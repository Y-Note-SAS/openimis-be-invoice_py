import graphene
import graphene_django_optimizer as gql_optimizer

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from core.schema import OrderedDjangoFilterConnectionField
from invoice.gql.row_filters import invoice_row_filters
from invoice.apps import InvoiceConfig
from invoice.gql.gql_types.payment_types import PaymentInvoiceGQLType
from invoice.models import PaymentInvoice


class PaymentInvoiceQueryMixin:
    payment_invoice = OrderedDjangoFilterConnectionField(
        PaymentInvoiceGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        subjectIds=graphene.List(of_type=graphene.UUID),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String(),
    )

    def resolve_payment_invoice(self, info, **kwargs):
        PaymentInvoiceQueryMixin._check_permissions(info.context.user)
        filters = []
        # records the legacy validity arguments on info.context for PaymentInvoice.get_queryset
        # (OP-2029): no filter to add here, the return value is not needed
        invoice_row_filters(info, kwargs, PaymentInvoice)

        query = PaymentInvoice.objects

        subject_ids = kwargs.get('subjectIds', None)
        if subject_ids:
            query = query.filter(
                invoice_payments__subject_id__in=subject_ids
            ).distinct()

        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        return gql_optimizer.query(query.filter(*filters).all(), info)

    @staticmethod
    def _check_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_payment_search_perms):
            raise PermissionError("Unauthorized")
