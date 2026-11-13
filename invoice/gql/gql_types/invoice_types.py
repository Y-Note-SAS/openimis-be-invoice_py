import graphene
import json
from django.core.serializers.json import DjangoJSONEncoder
from graphene_django import DjangoObjectType

from core import prefix_filterset, ExtendedConnection
from insuree.models import Insuree
from core.gql import ScopedQuerysetMixin
from invoice.gql.filter_mixin import GenericFilterGQLTypeMixin
from invoice.models import Invoice, InvoiceLineItem, InvoicePayment, InvoiceEvent, InvoiceMutation, \
    InvoicePaymentMutation, InvoiceLineItemMutation, InvoiceEventMutation
from invoice.utils import underscore_to_camel, related_summary


class InvoiceGQLType(ScopedQuerysetMixin, DjangoObjectType, GenericFilterGQLTypeMixin):
    subject = graphene.JSONString()
    subject_type = graphene.Int()
    subject_type_name = graphene.String()
    thirdparty = graphene.JSONString()
    thirdparty_type = graphene.Int()
    thirdparty_type_name = graphene.String()

    def resolve_subject_type(root, info):
        if root.subject_type:
            return root.subject_type.id

    def resolve_subject_type_name(root, info):
        if root.subject_type:
            return root.subject_type.name

    def resolve_thirdparty_type(root, info):
        if root.thirdparty_type:
            return root.thirdparty_type.id

    def resolve_thirdparty_type_name(root, info):
        if root.thirdparty_type:
            return root.thirdparty_type.name

    def resolve_subject(root, info):
        if root.subject:
            # identifying fields only, not the whole row of the subject
            subject_object_dict = related_summary(root.subject)
            if root.subject_type.name == "family" and subject_object_dict.get('headInsureeId'):
                insuree = Insuree.objects.filter(id=subject_object_dict['headInsureeId'], validity_to__isnull=True)
                insuree = insuree.values('id', 'chf_id', 'uuid', 'last_name', 'other_names')
                subject_object_dict['headInsuree'] = {
                    underscore_to_camel(k): v for k, v in insuree.first().items()
                }
            subject_object_dict = json.dumps(subject_object_dict, cls=DjangoJSONEncoder)
            return subject_object_dict

    def resolve_thirdparty(root, info):
        if root.thirdparty:
            # identifying fields only: the head insuree of a policy invoice, not their row
            thirdparty_object_dict = related_summary(root.thirdparty)
            thirdparty_object_dict = json.dumps(thirdparty_object_dict, cls=DjangoJSONEncoder)
            return thirdparty_object_dict

    class Meta:
        model = Invoice
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **GenericFilterGQLTypeMixin.get_base_filters_invoice(),
            "date_invoice": ["exact", "lt", "lte", "gt", "gte"],
        }

        connection_class = ExtendedConnection


class InvoiceLineItemGQLType(ScopedQuerysetMixin, DjangoObjectType, GenericFilterGQLTypeMixin):
    line = graphene.JSONString()
    line_type = graphene.Int()
    line_type_name = graphene.String()

    def resolve_line_type(root, info):
        if root.line_type:
            return root.line_type.id

    def resolve_line_type_name(root, info):
        if root.line_type:
            return root.line_type.name

    def resolve_line(root, info):
        if root.line:
            line_object_dict = root.line.__dict__
            line_object_dict.pop('_state')
            key_values = list(line_object_dict.items())
            line_object_dict.clear()
            for k, v in key_values:
                new_key = underscore_to_camel(k)
                line_object_dict[new_key] = v
            line_object_dict = json.dumps(line_object_dict, cls=DjangoJSONEncoder)
            return line_object_dict

    class Meta:
        model = InvoiceLineItem
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **GenericFilterGQLTypeMixin.get_base_filters_invoice_line_item(),
            **prefix_filterset("invoice__", InvoiceGQLType._meta.filter_fields),
        }

        connection_class = ExtendedConnection


class InvoicePaymentGQLType(ScopedQuerysetMixin, DjangoObjectType, GenericFilterGQLTypeMixin):
    class Meta:
        model = InvoicePayment
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **GenericFilterGQLTypeMixin.get_base_filters_invoice_payment(),
            **prefix_filterset("invoice__", InvoiceGQLType._meta.filter_fields),
        }

        connection_class = ExtendedConnection


class InvoiceEventGQLType(ScopedQuerysetMixin, DjangoObjectType, GenericFilterGQLTypeMixin):
    class Meta:
        model = InvoiceEvent
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **GenericFilterGQLTypeMixin.get_base_filters_invoice_event(),
            **prefix_filterset("invoice__", InvoiceGQLType._meta.filter_fields),
        }

        connection_class = ExtendedConnection


class InvoiceMutationGQLType(DjangoObjectType):
    class Meta:
        model = InvoiceMutation


class InvoicePaymentMutationGQLType(DjangoObjectType):
    class Meta:
        model = InvoicePaymentMutation


class InvoiceLineItemMutationGQLType(DjangoObjectType):
    class Meta:
        model = InvoiceLineItemMutation


class InvoiceEventMutationGQLType(DjangoObjectType):
    class Meta:
        model = InvoiceEventMutation
