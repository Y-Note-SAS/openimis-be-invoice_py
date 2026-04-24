import base64
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

import graphene
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType

from invoice.apps import InvoiceConfig
from invoice.models import DetailPaymentInvoice, Invoice
from insuree.models import Insuree


class InvoicePaymentItemGQLType(graphene.ObjectType):
    payment_id = graphene.UUID(required=True)
    payment_date = graphene.Date()
    payment_amount = graphene.Decimal()
    payment_reference = graphene.String()


class FamilyInvoicePaymentOverviewItemGQLType(graphene.ObjectType):
    row_id = graphene.String(required=True)
    invoice_id = graphene.UUID(required=True)
    invoice_code = graphene.String()
    covered_from = graphene.Date()
    covered_to = graphene.Date()
    amount_due = graphene.Decimal()
    total_invoice_payments = graphene.Decimal()
    invoice_balance = graphene.Decimal()
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
    total_invoice_amount = graphene.Decimal()
    total_paid_amount = graphene.Decimal()
    global_balance = graphene.Decimal()


class FamilyInvoicePaymentOverviewQueryMixin:
    family_invoice_payment_overview = graphene.Field(
        FamilyInvoicePaymentOverviewGQLType,
        head_insuree_id=graphene.String(required=True),
        first=graphene.Int(),
        after=graphene.String(),
        before=graphene.String(),
        last=graphene.Int(),
    )

    invoice_payments = graphene.List(
        InvoicePaymentItemGQLType,
        invoice_id=graphene.String(required=True),
        head_insuree_id=graphene.String(required=False),
    )

    def resolve_family_invoice_payment_overview(self, info, **kwargs):
        FamilyInvoicePaymentOverviewQueryMixin._check_permissions(info.context.user)

        head_insuree_id = kwargs.get("head_insuree_id")
        if not head_insuree_id:
            return FamilyInvoicePaymentOverviewQueryMixin._empty_overview()

        subject_ids = FamilyInvoicePaymentOverviewQueryMixin._normalize_head_insuree_subject_ids(head_insuree_id)
        if not subject_ids:
            return FamilyInvoicePaymentOverviewQueryMixin._empty_overview()

        invoice_queryset = Invoice.objects.filter(
            subject_type__model="insuree",
            subject_id__in=subject_ids,
            thirdparty_type__model="insuree",
            thirdparty_id__in=subject_ids,
            is_deleted=False,
        ).order_by("date_invoice", "id")

        if InvoiceConfig.invoice_user_filter:
            invoice_queryset = InvoiceConfig.invoice_user_filter(invoice_queryset, info.context.user)

        invoices = list(invoice_queryset)
        if not invoices:
            return FamilyInvoicePaymentOverviewQueryMixin._empty_overview()

        invoice_payment_details_by_invoice_id = FamilyInvoicePaymentOverviewQueryMixin._get_invoice_payment_details_by_invoice_id(invoices)

        total_invoice_amount = sum(Decimal(invoice.amount_total or 0) for invoice in invoices)
        total_paid_amount = sum(
            Decimal(payment_detail.amount or 0)
            for payment_details in invoice_payment_details_by_invoice_id.values()
            for payment_detail in payment_details
        )
        global_balance = total_invoice_amount - total_paid_amount

        invoice_rows = []
        for invoice in invoices:
            payment_details = invoice_payment_details_by_invoice_id.get(str(invoice.id), [])
            amount_due = Decimal(invoice.amount_total or 0)
            total_invoice_payments = sum(Decimal(payment_detail.amount or 0) for payment_detail in payment_details)
            invoice_balance = amount_due - total_invoice_payments
            invoice_rows.append(
                FamilyInvoicePaymentOverviewItemGQLType(
                    row_id=f"invoice-{invoice.id}",
                    invoice_id=invoice.id,
                    invoice_code=invoice.code,
                    covered_from=invoice.date_valid_from,
                    covered_to=invoice.date_valid_to,
                    amount_due=amount_due,
                    total_invoice_payments=total_invoice_payments,
                    invoice_balance=invoice_balance,
                    has_invoice_payments=bool(payment_details),
                )
            )

        total_count = len(invoice_rows)
        page_rows, page_info = FamilyInvoicePaymentOverviewQueryMixin._paginate_rows(invoice_rows, kwargs)

        return FamilyInvoicePaymentOverviewGQLType(
            total_count=total_count,
            page_info=FamilyInvoicePaymentOverviewPageInfoGQLType(**page_info),
            items=page_rows,
            total_invoice_amount=total_invoice_amount,
            total_paid_amount=total_paid_amount,
            global_balance=global_balance,
        )

    def resolve_invoice_payments(self, info, **kwargs):
        FamilyInvoicePaymentOverviewQueryMixin._check_permissions(info.context.user)

        invoice_id = kwargs.get("invoice_id")
        head_insuree_id = kwargs.get("head_insuree_id")
        if not invoice_id:
            return []

        invoice_scope_filter = {
            "id": str(invoice_id),
            "subject_type__model": "insuree",
            "thirdparty_type__model": "insuree",
            "is_deleted": False,
        }
        if head_insuree_id:
            subject_ids = FamilyInvoicePaymentOverviewQueryMixin._normalize_head_insuree_subject_ids(head_insuree_id)
            if not subject_ids:
                return []
            invoice_scope_filter["subject_id__in"] = subject_ids
            invoice_scope_filter["thirdparty_id__in"] = subject_ids

        invoice_matches_scope = Invoice.objects.filter(**invoice_scope_filter).exists()
        if not invoice_matches_scope:
            return []

        invoice_content_type = ContentType.objects.get_for_model(Invoice)
        invoice_payment_details = (
            DetailPaymentInvoice.objects.filter(
                subject_type=invoice_content_type,
                subject_id=str(invoice_id),
                is_deleted=False,
                payment__is_deleted=False,
            )
            .select_related("payment")
            .order_by("payment__date_payment", "payment__id")
        )

        return [
            InvoicePaymentItemGQLType(
                payment_id=payment_detail.payment.id,
                payment_date=payment_detail.payment.date_payment,
                payment_amount=Decimal(payment_detail.amount or 0),
                payment_reference=payment_detail.payment.code_ext,
            )
            for payment_detail in invoice_payment_details
        ]

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
            total_invoice_amount=Decimal("0"),
            total_paid_amount=Decimal("0"),
            global_balance=Decimal("0"),
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
                payment__is_deleted=False,
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
