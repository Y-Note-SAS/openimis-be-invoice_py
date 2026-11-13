import graphene
import graphene_django_optimizer as gql_optimizer

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from core.schema import OrderedDjangoFilterConnectionField
from invoice.gql.row_filters import invoice_row_filters
from invoice.apps import InvoiceConfig
from invoice.gql.gql_types.payment_types import DetailPaymentInvoiceGQLType
from invoice.models import DetailPaymentInvoice


class DetailPaymentInvoiceQueryMixin:
    detail_payment_invoice = OrderedDjangoFilterConnectionField(
        DetailPaymentInvoiceGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String(),
    )

    def resolve_detail_payment_invoice(self, info, **kwargs):
        DetailPaymentInvoiceQueryMixin._check_permissions(info.context.user)
        filters = []
        # records the legacy validity arguments on info.context for DetailPaymentInvoice.get_queryset
        # (OP-2029): no filter to add here, the return value is not needed
        invoice_row_filters(info, kwargs, DetailPaymentInvoice)

        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        return gql_optimizer.query(DetailPaymentInvoice.objects.filter(*filters).all(), info)

    @staticmethod
    def _check_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_payment_search_perms):
            raise PermissionError("Unauthorized")
