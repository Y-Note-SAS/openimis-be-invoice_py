import graphene
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from core.schema import OrderedDjangoFilterConnectionField
from invoice.gql.row_filters import invoice_row_filters
from invoice.apps import InvoiceConfig
from invoice.gql.gql_types.bill_types import BillPaymentGQLType
from invoice.models import BillPayment, Bill
import graphene_django_optimizer as gql_optimizer


class BillPaymentQueryMixin:
    bill_payment = OrderedDjangoFilterConnectionField(
        BillPaymentGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String(),
    )

    def resolve_bill_payment(self, info, **kwargs):
        BillPaymentQueryMixin._check_permissions(info.context.user)
        filters = []
        # records the legacy validity arguments on info.context for BillPayment.get_queryset
        # (OP-2029): no filter to add here, the return value is not needed
        invoice_row_filters(info, kwargs, BillPayment)

        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        bill_payment_qs = BillPayment.objects.filter(*filters)

        if InvoiceConfig.bill_user_filter:
            bill_qs = InvoiceConfig.bill_user_filter(Bill.objects.all(), info.context.user)
            bill_payment_qs = bill_payment_qs.filter(bill__in=bill_qs)

        return gql_optimizer.query(bill_payment_qs, info)

    @staticmethod
    def _check_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_bill_payment_search_perms):
            raise PermissionError("Unauthorized")
