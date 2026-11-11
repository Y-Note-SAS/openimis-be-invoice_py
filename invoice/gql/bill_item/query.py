import graphene
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from core.schema import OrderedDjangoFilterConnectionField
from invoice.gql.row_filters import invoice_row_filters
from invoice.apps import InvoiceConfig
from invoice.gql.gql_types.bill_types import BillItemGQLType
from invoice.models import BillItem, Bill
import graphene_django_optimizer as gql_optimizer


class BillItemQueryMixin:
    bill_item = OrderedDjangoFilterConnectionField(
        BillItemGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String(),
    )

    def resolve_bill_item(self, info, **kwargs):
        BillItemQueryMixin._check_permissions(info.context.user)
        filters = []
        # validity applied by BillItem.get_queryset, scoped by its type (OP-2029)
        invoice_row_filters(info, kwargs, BillItem)

        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        line_type = kwargs.get("line_type", None)
        if line_type:
            filters.append(Q(line_type__model=line_type))

        bill_li_qs = BillItem.objects.filter(*filters)

        if InvoiceConfig.bill_user_filter:
            bill_qs = InvoiceConfig.bill_user_filter(Bill.objects.all(), info.context.user)
            bill_li_qs = bill_li_qs.filter(bill__in=bill_qs)

        return gql_optimizer.query(bill_li_qs, info)

    @staticmethod
    def _check_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_bill_search_perms):
            raise PermissionError("Unauthorized")
