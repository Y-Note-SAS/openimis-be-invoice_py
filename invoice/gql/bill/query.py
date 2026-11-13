import graphene
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from pandas import DataFrame

from core.gql.export_mixin import ExportableQueryMixin
from core.schema import OrderedDjangoFilterConnectionField
from invoice.gql.row_filters import invoice_row_filters
from invoice.apps import InvoiceConfig
from invoice.gql.gql_types.bill_types import BillGQLType
from invoice.models import Bill
import graphene_django_optimizer as gql_optimizer

from policy.models import Policy


def patch_subjects(bills_df: DataFrame):
    subject_df = bills_df[['subject_type', 'subject_id']].drop_duplicates()
    bills_df['subject_class'] = 'undefined'
    for subject in subject_df['subject_type'].unique():
        model = ContentType.objects.get(id=subject).model_class()
        entities_for_model = subject_df[subject_df['subject_type'] == subject]['subject_id']
        if model == Policy:
            subject_names = model.objects \
                .filter(id__in=entities_for_model) \
                .values('id', 'family__head_insuree__chf_id',
                        'family__head_insuree__last_name', 'family__head_insuree__other_names')
            names = {
                str(x['id']): F"{x['family__head_insuree__other_names']} {x['family__head_insuree__last_name']} ({x['family__head_insuree__chf_id']})"
                for x in subject_names
            }
            updated = bills_df['subject_type'] == subject
            bills_df.loc[updated, 'subject_id'] = bills_df[updated]['subject_id'].apply(lambda x: names[x])
        bills_df.loc[bills_df['subject_type'] == subject, 'subject_class'] = model.__name__
        bills_df['subject_type'] = bills_df.pop('subject_class')
    return bills_df


class BillQueryMixin(ExportableQueryMixin):
    export_patches = {
        'bill': [
            patch_subjects
        ]
    }

    exportable_fields = ['bill']
    bill = OrderedDjangoFilterConnectionField(
        BillGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String(),
    )

    def resolve_bill(self, info, **kwargs):
        BillQueryMixin._check_permissions(info.context.user)
        filters = []
        # records the legacy validity arguments on info.context for Bill.get_queryset
        # (OP-2029): no filter to add here, the return value is not needed
        invoice_row_filters(info, kwargs, Bill)

        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        subject_type = kwargs.get("subject_type", None)
        if subject_type:
            filters.append(Q(subject_type__model=subject_type))

        thirdparty_type = kwargs.get("thirdparty_type", None)
        if thirdparty_type:
            filters.append(Q(thirdparty_type__model=thirdparty_type))

        qs = Bill.objects.filter(*filters)
        if InvoiceConfig.bill_user_filter:
            qs = InvoiceConfig.bill_user_filter(qs, info.context.user)

        return gql_optimizer.query(qs, info)

    @staticmethod
    def _check_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_bill_search_perms):
            raise PermissionError("Unauthorized")
