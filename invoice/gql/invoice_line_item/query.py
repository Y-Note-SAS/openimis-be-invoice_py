import graphene
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from core.schema import OrderedDjangoFilterConnectionField
from invoice.gql.row_filters import invoice_row_filters
from invoice.apps import InvoiceConfig
from invoice.gql.gql_types.invoice_types import InvoiceLineItemGQLType
from invoice.models import InvoiceLineItem, Invoice
import graphene_django_optimizer as gql_optimizer


class InvoiceLineItemQueryMixin:
    invoice_line_item = OrderedDjangoFilterConnectionField(
        InvoiceLineItemGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String(),
    )

    def resolve_invoice_line_item(self, info, **kwargs):
        InvoiceLineItemQueryMixin._check_invoice_permissions(info.context.user)
        filters = []
        # records the legacy validity arguments on info.context for InvoiceLineItem.get_queryset
        # (OP-2029): no filter to add here, the return value is not needed
        invoice_row_filters(info, kwargs, InvoiceLineItem)

        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        line_type = kwargs.get("line_type", None)
        if line_type:
            filters.append(Q(line_type__model=line_type))

        invoice_li_qs = InvoiceLineItem.objects.filter(*filters)

        if InvoiceConfig.invoice_user_filter:
            invoice_qs = InvoiceConfig.invoice_user_filter(Invoice.objects.all(), info.context.user)
            invoice_li_qs = invoice_li_qs.filter(invoice__in=invoice_qs)

        return gql_optimizer.query(invoice_li_qs, info)

    @staticmethod
    def _check_invoice_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_search_perms):
            raise PermissionError("Unauthorized")
