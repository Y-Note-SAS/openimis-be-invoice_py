import base64
import hashlib
import json
import logging
import time
from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

import graphene
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache

from invoice.apps import InvoiceConfig
from invoice.models import DetailPaymentInvoice, Invoice
from insuree.models import Insuree

logger = logging.getLogger(__name__)


class FamilyInvoicePaymentOverviewItemGQLType(graphene.ObjectType):
    row_id = graphene.String(required=True)
    invoice_id = graphene.UUID(required=True)
    invoice_code = graphene.String()
    covered_from = graphene.Date()
    covered_to = graphene.Date()
    amount_due = graphene.Decimal()
    total_invoice_payments = graphene.Decimal()
    invoice_balance = graphene.Decimal()
    last_payment = graphene.Date()
    has_invoice_payments = graphene.Boolean(required=True)


class FamilyInvoicePaymentOverviewPageInfoGQLType(graphene.ObjectType):
    has_next_page = graphene.Boolean(required=True)
    has_previous_page = graphene.Boolean(required=True)
    start_cursor = graphene.String()
    end_cursor = graphene.String()


class FamilyInvoicePaymentOverviewGQLType(graphene.ObjectType):
    total_count = graphene.Int(required=True)
    page_info = graphene.Field(FamilyInvoicePaymentOverviewPageInfoGQLType, required=True)
    items = graphene.List(FamilyInvoicePaymentOverviewItemGQLType, required=True)


class FamilyInvoicePaymentGlobalsGQLType(graphene.ObjectType):
    total_invoice_amount = graphene.Decimal(required=True)
    total_paid_amount = graphene.Decimal(required=True)
    global_balance = graphene.Decimal(required=True)


class FamilyInvoicePaymentOverviewQueryMixin:
    SNAPSHOT_CACHE_KEY_PREFIX = "family_invoice_payment_snapshot"
    SNAPSHOT_CACHE_CODE_VERSION = "v1"
    SNAPSHOT_CACHE_TTL_SECONDS = getattr(settings, "INVOICE_FAMILY_OVERVIEW_CACHE_TTL_SECONDS", 180)
    SNAPSHOT_CACHE_MAX_ROWS = getattr(settings, "INVOICE_FAMILY_OVERVIEW_CACHE_MAX_ROWS", 10000)
    SNAPSHOT_CACHE_ENABLED = getattr(settings, "INVOICE_FAMILY_OVERVIEW_CACHE_ENABLED", True)

    family_invoice_payment_overview = graphene.Field(
        FamilyInvoicePaymentOverviewGQLType,
        head_insuree_id=graphene.String(required=True),
        first=graphene.Int(),
        after=graphene.String(),
        before=graphene.String(),
        last=graphene.Int(),
    )
    family_invoice_payment_globals = graphene.Field(
        FamilyInvoicePaymentGlobalsGQLType,
        head_insuree_id=graphene.String(required=True),
    )

    def resolve_family_invoice_payment_overview(self, info, **kwargs):
        FamilyInvoicePaymentOverviewQueryMixin._check_permissions(info.context.user)

        head_insuree_id = kwargs.get("head_insuree_id")
        if not head_insuree_id:
            return FamilyInvoicePaymentOverviewQueryMixin._empty_overview()

        snapshot = FamilyInvoicePaymentOverviewQueryMixin._get_or_build_snapshot(info.context.user, head_insuree_id)
        if not snapshot:
            return FamilyInvoicePaymentOverviewQueryMixin._empty_overview()
        page_slice_start = time.perf_counter()
        total_count = snapshot["total_count"]
        page_rows_dicts, page_info = FamilyInvoicePaymentOverviewQueryMixin._paginate_rows(snapshot["rows"], kwargs)
        page_rows = [FamilyInvoicePaymentOverviewQueryMixin._row_dict_to_gql(row) for row in page_rows_dicts]
        logger.info(
            "family_invoice_payment_overview page_slice_ms=%.2f rows_count=%s",
            (time.perf_counter() - page_slice_start) * 1000,
            total_count,
        )

        return FamilyInvoicePaymentOverviewGQLType(
            total_count=total_count,
            page_info=FamilyInvoicePaymentOverviewPageInfoGQLType(**page_info),
            items=page_rows,
        )

    def resolve_family_invoice_payment_globals(self, info, **kwargs):
        FamilyInvoicePaymentOverviewQueryMixin._check_permissions(info.context.user)

        head_insuree_id = kwargs.get("head_insuree_id")
        if not head_insuree_id:
            return FamilyInvoicePaymentGlobalsGQLType(
                total_invoice_amount=Decimal("0"),
                total_paid_amount=Decimal("0"),
                global_balance=Decimal("0"),
            )

        snapshot = FamilyInvoicePaymentOverviewQueryMixin._get_or_build_snapshot(info.context.user, head_insuree_id)
        if not snapshot:
            return FamilyInvoicePaymentGlobalsGQLType(
                total_invoice_amount=Decimal("0"),
                total_paid_amount=Decimal("0"),
                global_balance=Decimal("0"),
            )
        total_invoice_amount = Decimal(snapshot["totals"]["total_invoice_amount"])
        total_paid_amount = Decimal(snapshot["totals"]["total_paid_amount"])
        return FamilyInvoicePaymentGlobalsGQLType(
            total_invoice_amount=total_invoice_amount,
            total_paid_amount=total_paid_amount,
            global_balance=total_invoice_amount - total_paid_amount,
        )

    @classmethod
    def _get_or_build_snapshot(cls, user, head_insuree_id):
        subject_ids = cls._normalize_head_insuree_subject_ids(head_insuree_id)
        if not subject_ids:
            return None
        cache_key = cls._snapshot_cache_key(user, head_insuree_id, subject_ids)
        if cls.SNAPSHOT_CACHE_ENABLED:
            try:
                cached_snapshot = cache.get(cache_key)
                if cached_snapshot is not None:
                    logger.info("family_invoice_payment_snapshot cache_hit key=%s", cache_key)
                    return cached_snapshot
            except Exception:
                logger.exception("family_invoice_payment_snapshot cache_get_error key=%s", cache_key)
        logger.info("family_invoice_payment_snapshot cache_miss key=%s", cache_key)
        build_start = time.perf_counter()
        snapshot = cls._build_snapshot(user, subject_ids)
        logger.info(
            "family_invoice_payment_snapshot build_ms=%.2f rows_count=%s",
            (time.perf_counter() - build_start) * 1000,
            snapshot["total_count"] if snapshot else 0,
        )
        if not snapshot:
            return None
        if cls.SNAPSHOT_CACHE_ENABLED and snapshot["total_count"] <= cls.SNAPSHOT_CACHE_MAX_ROWS:
            try:
                cache.set(cache_key, snapshot, timeout=cls.SNAPSHOT_CACHE_TTL_SECONDS)
            except Exception:
                logger.exception("family_invoice_payment_snapshot cache_set_error key=%s", cache_key)
        return snapshot

    @classmethod
    def _build_snapshot(cls, user, subject_ids):
        invoice_queryset = Invoice.objects.filter(
            subject_type__model="insuree",
            subject_id__in=subject_ids,
            thirdparty_type__model="insuree",
            thirdparty_id__in=subject_ids,
            is_deleted=False,
        ).order_by("date_invoice", "id")
        if InvoiceConfig.invoice_user_filter:
            invoice_queryset = InvoiceConfig.invoice_user_filter(invoice_queryset, user)
        invoices = list(invoice_queryset)
        if not invoices:
            return None
        invoice_payment_details_by_invoice_id = cls._get_invoice_payment_details_by_invoice_id(invoices)
        total_invoice_amount = sum(Decimal(invoice.amount_total or 0) for invoice in invoices)
        total_paid_amount = sum(
            Decimal(payment_detail.amount or 0)
            for payment_details in invoice_payment_details_by_invoice_id.values()
            for payment_detail in payment_details
        )
        rows = []
        for invoice in invoices:
            payment_details = invoice_payment_details_by_invoice_id.get(str(invoice.id), [])
            amount_due = Decimal(invoice.amount_total or 0)
            total_invoice_payments = sum(Decimal(payment_detail.amount or 0) for payment_detail in payment_details)
            invoice_balance = amount_due - total_invoice_payments
            last_payment = payment_details[-1].payment.date_payment if payment_details else None
            rows.append(
                {
                    "row_id": f"invoice-{invoice.id}",
                    "invoice_id": str(invoice.id),
                    "invoice_code": invoice.code,
                    "covered_from": invoice.date_valid_from.isoformat() if invoice.date_valid_from else None,
                    "covered_to": invoice.date_valid_to.isoformat() if invoice.date_valid_to else None,
                    "amount_due": str(amount_due),
                    "total_invoice_payments": str(total_invoice_payments),
                    "invoice_balance": str(invoice_balance),
                    "last_payment": last_payment.isoformat() if last_payment else None,
                    "has_invoice_payments": bool(payment_details),
                }
            )
        return {
            "rows": rows,
            "total_count": len(rows),
            "totals": {
                "total_invoice_amount": str(total_invoice_amount),
                "total_paid_amount": str(total_paid_amount),
                "global_balance": str(total_invoice_amount - total_paid_amount),
            },
        }

    @classmethod
    def _snapshot_cache_key(cls, user, head_insuree_id, subject_ids):
        key_payload = {
            "user_id": user.id,
            "head_insuree_id": str(head_insuree_id),
            "subject_ids": sorted([str(subject_id) for subject_id in subject_ids]),
            "code_version": cls.SNAPSHOT_CACHE_CODE_VERSION,
        }
        key_hash = hashlib.sha256(
            json.dumps(key_payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return f"{cls.SNAPSHOT_CACHE_KEY_PREFIX}:{user.id}:{head_insuree_id}:{key_hash}"

    @staticmethod
    def _row_dict_to_gql(row):
        def _to_date(value):
            if not value:
                return None
            if isinstance(value, date):
                return value
            value_str = str(value)
            if "T" in value_str:
                value_str = value_str.split("T", 1)[0]
            return date.fromisoformat(value_str)

        return FamilyInvoicePaymentOverviewItemGQLType(
            row_id=row["row_id"],
            invoice_id=row["invoice_id"],
            invoice_code=row.get("invoice_code"),
            covered_from=_to_date(row.get("covered_from")),
            covered_to=_to_date(row.get("covered_to")),
            amount_due=Decimal(row.get("amount_due") or "0"),
            total_invoice_payments=Decimal(row.get("total_invoice_payments") or "0"),
            invoice_balance=Decimal(row.get("invoice_balance") or "0"),
            last_payment=_to_date(row.get("last_payment")),
            has_invoice_payments=bool(row.get("has_invoice_payments")),
        )

    @staticmethod
    def _empty_overview():
        return FamilyInvoicePaymentOverviewGQLType(
            total_count=0,
            page_info=FamilyInvoicePaymentOverviewPageInfoGQLType(
                has_next_page=False,
                has_previous_page=False,
                start_cursor=None,
                end_cursor=None,
            ),
            items=[],
        )

    @staticmethod
    def _get_invoice_payment_details_by_invoice_id(invoices):
        invoice_content_type = ContentType.objects.get_for_model(Invoice)
        invoice_ids = [invoice.id for invoice in invoices]

        invoice_payment_details_queryset = (
            DetailPaymentInvoice.objects.filter(
                subject_type=invoice_content_type,
                subject_id__in=invoice_ids,
                is_deleted=False,
                payment__is_deleted=False
            )
            .select_related("payment")
            .order_by("payment__date_payment", "payment__id")
        )

        invoice_payment_details_by_invoice_id = defaultdict(list)
        for payment_detail in invoice_payment_details_queryset:
            invoice_payment_details_by_invoice_id[str(payment_detail.subject_id)].append(payment_detail)

        return invoice_payment_details_by_invoice_id

    @staticmethod
    def _check_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(InvoiceConfig.gql_invoice_search_perms):
            raise PermissionError("Unauthorized")

    @staticmethod
    def _normalize_head_insuree_subject_ids(head_insuree_id):
        raw_value = str(head_insuree_id).strip()
        if not raw_value:
            return []

        subject_ids = {raw_value}
        try:
            UUID(raw_value)
            insuree = Insuree.objects.filter(uuid=raw_value, validity_to__isnull=True).only("id").first()
            if insuree:
                subject_ids.add(str(insuree.id))
        except ValueError:
            pass

        return list(subject_ids)

    @staticmethod
    def _encode_cursor(index):
        return base64.b64encode(f"cursor:{index}".encode("utf-8")).decode("utf-8")

    @staticmethod
    def _decode_cursor(cursor):
        if not cursor:
            return None
        try:
            decoded = base64.b64decode(cursor).decode("utf-8")
            prefix, value = decoded.split(":", 1)
            if prefix != "cursor":
                return None
            return int(value)
        except Exception:
            return None

    @classmethod
    def _paginate_rows(cls, rows, kwargs):
        total = len(rows)
        first = kwargs.get("first")
        after = kwargs.get("after")
        before = kwargs.get("before")
        last = kwargs.get("last")

        start = 0
        end = total

        after_index = cls._decode_cursor(after)
        if after_index is not None:
            start = min(total, after_index + 1)

        before_index = cls._decode_cursor(before)
        if before_index is not None:
            end = max(0, min(end, before_index))

        window = rows[start:end]
        if first is not None:
            take = max(0, first)
            page_start_offset = 0
            page_rows = window[:take]
        elif last is not None:
            take = max(0, last)
            page_start_offset = max(0, len(window) - take)
            page_rows = window[-take:]
        else:
            page_start_offset = 0
            page_rows = window

        if not page_rows:
            return page_rows, {
                "has_next_page": end < total,
                "has_previous_page": start > 0,
                "start_cursor": None,
                "end_cursor": None,
            }

        first_index = start + page_start_offset
        last_index = first_index + len(page_rows) - 1

        return page_rows, {
            "has_next_page": last_index < total - 1,
            "has_previous_page": first_index > 0,
            "start_cursor": cls._encode_cursor(first_index),
            "end_cursor": cls._encode_cursor(last_index),
        }
