import graphene
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from core.schema import OrderedDjangoFilterConnectionField
from invoice.gql.row_filters import invoice_row_filters
from invoice.apps import InvoiceConfig
from invoice.gql.gql_types.invoice_types import InvoiceGQLType
from invoice.models import Invoice
import graphene_django_optimizer as gql_optimizer


class InvoiceQueryMixin:
    invoice = OrderedDjangoFilterConnectionField(
        InvoiceGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String()
    )

    def resolve_invoice(self, info, **kwargs):
        InvoiceQueryMixin._check_permissions(info.context.user)
        filters = []
        # validity applied by Invoice.get_queryset, scoped by its type (OP-2029)
        invoice_row_filters(info, kwargs, Invoice)

        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        subject_type = kwargs.get("subject_type", None)
        if subject_type:
            filters.append(Q(subject_type__model=subject_type))

        thirdparty_type = kwargs.get("thirdparty_type", None)
        if thirdparty_type:
            filters.append(Q(thirdparty_type__model=thirdparty_type))

        qs = Invoice.objects.filter(*filters)
        if InvoiceConfig.invoice_user_filter:
            qs = InvoiceConfig.invoice_user_filter(qs, info.context.user)

        return gql_optimizer.query(qs, info)

    @staticmethod
    def _check_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_search_perms):
            raise PermissionError("Unauthorized")
