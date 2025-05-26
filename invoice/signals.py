from core.signals import bind_service_signal
from core.service_signals import ServiceSignalBindType
from django.contrib.contenttypes.models import ContentType
from invoice.models import InvoiceLineItem
from invoice.services import InvoiceService
from .apps import InvoiceConfig


def bind_service_signals():
    bind_service_signal(
        'convert_to_invoice',
        check_invoice_exist,
        bind_type=ServiceSignalBindType.BEFORE
    )
    bind_service_signal(
        'convert_to_invoice',
        save_invoice_in_db,
        bind_type=ServiceSignalBindType.AFTER
    )


def check_invoice_exist(**kwargs):
    function_arguments = kwargs.get('data')[1]
    instance = function_arguments.get('instance', None)
    content_type_policy = ContentType.objects.get_for_model(instance.__class__)
    invoices = InvoiceLineItem.objects.filter(line_type=content_type_policy, line_id=instance.id)
    if invoices.count() == 0:
        return True


def save_invoice_in_db(**kwargs):
    if str(kwargs.get('sender')) == "<class 'calcrule_contribution_legacy.calculation_rule.ContributionPlanCalculationRuleProductModeling'>":
        if InvoiceConfig.system_generate_invoice_on_policy:
            InvoiceService.invoice_create(**kwargs)
    else:
        InvoiceService.invoice_create(**kwargs)
