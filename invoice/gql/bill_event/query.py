import graphene
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from core.schema import OrderedDjangoFilterConnectionField
from invoice.gql.row_filters import invoice_row_filters
from invoice.apps import InvoiceConfig
from invoice.gql.gql_types.bill_types import BillEventGQLType
from invoice.models import BillEvent, Bill
import graphene_django_optimizer as gql_optimizer


class BillEventQueryMixin:
    bill_event = OrderedDjangoFilterConnectionField(
        BillEventGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String(),
    )

    def resolve_bill_event(self, info, **kwargs):
        BillEventQueryMixin._check_permissions(info.context.user)
        filters = []
        # validity applied by BillEvent.get_queryset, scoped by its type (OP-2029)
        invoice_row_filters(info, kwargs, BillEvent)

        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        bill_event_qs = BillEvent.objects.filter(*filters)

        if InvoiceConfig.bill_user_filter:
            bill_qs = InvoiceConfig.bill_user_filter(Bill.objects.all(), info.context.user)
            bill_event_qs = bill_event_qs.filter(bill__in=bill_qs)

        return gql_optimizer.query(bill_event_qs, info)

    @staticmethod
    def _check_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_bill_event_search_perms):
            raise PermissionError("Unauthorized")
