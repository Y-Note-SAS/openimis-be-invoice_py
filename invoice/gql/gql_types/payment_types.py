import json
import graphene

from django.core.serializers.json import DjangoJSONEncoder
from graphene_django import DjangoObjectType
from core import prefix_filterset, ExtendedConnection
from invoice.apps import InvoiceConfig
from invoice.gql.filter_mixin import GenericFilterGQLTypeMixin
from invoice.models import PaymentInvoice, DetailPaymentInvoice
from invoice.utils import underscore_to_camel
from django.forms.models import model_to_dict
from django.utils.translation import gettext as _
from django.core.exceptions import PermissionDenied


class PaymentInvoiceGQLType(DjangoObjectType, GenericFilterGQLTypeMixin):
    party_type = graphene.Int()
    party_type_name = graphene.String()
    party = graphene.JSONString()
    payment_destination_type = graphene.Int()
    payment_destination_type_name = graphene.String()
    payment_destination = graphene.JSONString()

    def resolve_party_type(root, info):
        if root.party_type:
            return root.party_type.id

    def resolve_party_type_name(root, info):
        if root.party_type:
            return root.party_type.name

    def resolve_party(root, info):
        if root.party_type and root.party:
            data = model_to_dict(root.party)
            cleaned_data = {
                underscore_to_camel(k): v
                for k, v in data.items()
            }

            return json.loads(
                json.dumps(cleaned_data, cls=DjangoJSONEncoder)
            )

        return None

    def resolve_payment_destination_type(root, info):
        if root.payment_destination_type:
            return root.payment_destination_type.id

    def resolve_payment_destination_type_name(root, info):
        if root.payment_destination_type:
            return root.payment_destination_type.name

    def resolve_payment_destination(root, info):
        if root.payment_destination_type and root.payment_destination:
            data = model_to_dict(root.payment_destination)

            cleaned_data = {
                underscore_to_camel(k): v
                for k, v in data.items()
            }

            return json.loads(
                json.dumps(cleaned_data, cls=DjangoJSONEncoder)
            )

        return None

    class Meta:
        model = PaymentInvoice
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **GenericFilterGQLTypeMixin.get_base_filters_payment_invoice(),
        }

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
