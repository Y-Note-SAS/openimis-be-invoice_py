import re

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from invoice.models import (
    DetailPaymentInvoice,
    Invoice,
    InvoiceLineItem,
    Bill,
    BillItem
)

camel_pat = re.compile(r'([A-Z])')
under_pat = re.compile(r'_([a-z])')


def camel_to_underscore(name):
    return camel_pat.sub(lambda x: '_' + x.group(1).lower(), name)


def underscore_to_camel(name):
    return under_pat.sub(lambda x: x.group(1).upper(), name)


def resolve_payment_details(payment_invoice):
    invoice_list = _retrieve_list_of_invoices_bills(payment_invoice, Invoice)
    invoice_line_item_list = _retrieve_list_of_invoices_bills(payment_invoice, InvoiceLineItem)
    invoices = Invoice.objects.filter(Q(id__in=invoice_list) | Q(line_items__id__in=invoice_line_item_list))
    bill_list = _retrieve_list_of_invoices_bills(payment_invoice, Bill)
    bill_line_item_list = _retrieve_list_of_invoices_bills(payment_invoice, BillItem)
    bills = Bill.objects.filter(Q(id__in=bill_list) | Q(line_items_bill__id__in=bill_line_item_list))
    return invoices, bills


def _retrieve_list_of_invoices_bills(payment_invoice, model_type):
    return list(DetailPaymentInvoice.objects.filter(
        payment=payment_invoice,
        subject_type=ContentType.objects.get_for_model(model_type).id
    ).values_list('subject_id', flat=True))


#: The fields of a related subject / third party (insuree, family, policy, health
#: facility, policy holder, batch run...) a bill or an invoice exposes: what identifies
#: and names it, never the whole row (an insuree's birth date, phone, address...).
RELATED_SUMMARY_FIELDS = (
    "id", "uuid", "code", "chf_id", "name", "trade_name", "last_name", "other_names",
    "run_year", "run_month", "run_date", "location_id", "head_insuree_id",
)


def related_summary(obj):
    """{camelCaseField: value} of the RELATED_SUMMARY_FIELDS `obj` has, nothing else."""
    if obj is None:
        return None
    summary = {}
    for name in RELATED_SUMMARY_FIELDS:
        try:
            value = getattr(obj, name)
        except (AttributeError, ObjectDoesNotExist):  # a missing field or relation is just absent
            continue
        if callable(value):
            continue
        summary[underscore_to_camel(name)] = value
    return summary
