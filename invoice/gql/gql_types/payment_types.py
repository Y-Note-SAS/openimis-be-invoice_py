import json
import graphene

from django.core.serializers.json import DjangoJSONEncoder
from graphene_django import DjangoObjectType

from core import prefix_filterset, ExtendedConnection
from invoice.apps import InvoiceConfig
from invoice.gql.filter_mixin import GenericFilterGQLTypeMixin
from invoice.models import PaymentInvoice, DetailPaymentInvoice
from invoice.utils import underscore_to_camel
from django.utils.translation import gettext as _
from django.core.exceptions import PermissionDenied
from django.conf import settings


class PaymentInvoiceGQLType(DjangoObjectType, GenericFilterGQLTypeMixin):
    party_type = graphene.Int()
    party_type_name = graphene.String()
    party = graphene.JSONString()
    payment_destination = graphene.Field(
        'ledger.gql_queries.LedgerJournalGQLType',
        required=False
    ) if 'ledgers' in settings.INSTALLED_APPS else graphene.String()

    def resolve_party_type(root, info):
        if root.party_type:
            return root.party_type.id

    def resolve_party_type_name(root, info):
        if root.party_type:
            return root.party_type.name

    def resolve_party(root, info):
        if root.party_type and root.party:
            thirdparty_object_dict = root.party.__dict__.copy()
            thirdparty_object_dict.pop('_state', None)

            cleaned_dict = {
                underscore_to_camel(k): v for k, v in thirdparty_object_dict.items()
            }
            return json.loads(json.dumps(cleaned_dict, cls=DjangoJSONEncoder))

        return None

    def resolve_payment_destination(self, info):
        # Renvoie l'UUID stocké, qu'il y ait FK ou non
        if 'ledgers' in settings.INSTALLED_APPS:
            from ledger.models import LedgerJournal
            try:
                return LedgerJournal.objects.get(pk=self.payment_destination)
            except LedgerJournal.DoesNotExist:
                return None
        if self.payment_destination:
            return str(self.payment_destination)
        return None

    class Meta:
        model = PaymentInvoice
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **GenericFilterGQLTypeMixin.get_base_filters_payment_invoice(),
        }
        exclude_fields = ('payment_destination',)

        connection_class = ExtendedConnection

        @classmethod
        def get_queryset(cls, queryset, info):
            return PaymentInvoice.get_queryset(queryset, info)


class DetailPaymentInvoiceGQLType(DjangoObjectType, GenericFilterGQLTypeMixin):

    subject_type = graphene.Int()
    def resolve_subject_type(root, info):
        if not info.context.user.has_perms(InvoiceConfig.gql_invoice_payment_search_perms):
            raise PermissionDenied(_("unauthorized"))
        return root.subject_type.id

    subject_type_name = graphene.String()
    def resolve_subject_type_name(root, info):
        if not info.context.user.has_perms(InvoiceConfig.gql_invoice_payment_search_perms):
            raise PermissionDenied(_("unauthorized"))
        return root.subject_type.name

    subject = graphene.JSONString()
    def resolve_subject(root, info):
        if not info.context.user.has_perms(InvoiceConfig.gql_invoice_payment_search_perms):
            raise PermissionDenied(_("unauthorized"))
        subject_object_dict = root.subject.__dict__
        subject_object_dict.pop('_state', None)
        subject_object_dict = {
            underscore_to_camel(k): v for k, v in list(subject_object_dict.items())
        }
        subject_object_dict = json.dumps(subject_object_dict, cls=DjangoJSONEncoder)
        return subject_object_dict

    class Meta:
        model = DetailPaymentInvoice
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **GenericFilterGQLTypeMixin.get_base_filters_detail_invoice_payment(),
            **prefix_filterset("payment__", PaymentInvoiceGQLType._meta.filter_fields),
        }

        connection_class = ExtendedConnection

        @classmethod
        def get_queryset(cls, queryset, info):
            return DetailPaymentInvoice.get_queryset(queryset, info)
