import graphene
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from core.schema import OrderedDjangoFilterConnectionField
from invoice.gql.row_filters import invoice_row_filters
from invoice.apps import InvoiceConfig
from invoice.gql.gql_types.invoice_types import InvoiceEventGQLType
from invoice.models import InvoiceEvent, Invoice
import graphene_django_optimizer as gql_optimizer


class InvoiceEventQueryMixin:
    invoice_event = OrderedDjangoFilterConnectionField(
        InvoiceEventGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String(),
    )

    def resolve_invoice_event(self, info, **kwargs):
        InvoiceEventQueryMixin._check_permissions(info.context.user)
        filters = []
        # records the legacy validity arguments on info.context for InvoiceEvent.get_queryset
        # (OP-2029): no filter to add here, the return value is not needed
        invoice_row_filters(info, kwargs, InvoiceEvent)

        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        invoice_event_qs = InvoiceEvent.objects.filter(*filters)

        if InvoiceConfig.invoice_user_filter:
            invoice_qs = InvoiceConfig.invoice_user_filter(Invoice.objects.all(), info.context.user)
            invoice_event_qs = invoice_event_qs.filter(invoice__in=invoice_qs)

        return gql_optimizer.query(invoice_event_qs, info)

    @staticmethod
    def _check_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_event_search_perms):
            raise PermissionError("Unauthorized")
