import graphene
import json
from django.core.serializers.json import DjangoJSONEncoder
from graphene_django import DjangoObjectType

from core import prefix_filterset, ExtendedConnection
from core.gql import ScopedQuerysetMixin
from invoice.gql.filter_mixin import GenericFilterGQLTypeMixin
from invoice.models import Bill, \
    BillItem, BillEvent, BillPayment
from invoice.utils import underscore_to_camel, related_summary
from location.models import Location


class BillGQLType(ScopedQuerysetMixin, DjangoObjectType, GenericFilterGQLTypeMixin):
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
            if root.subject_type.name == "batch run" and subject_object_dict.get('locationId', None):
                location = Location.objects.filter(id=subject_object_dict['locationId'], validity_to__isnull=True)
                location = location.values('code', 'name').first()
                if location:
                    subject_object_dict['location'] = {
                        underscore_to_camel(k): v for k, v in location.items()
                    }
            subject_object_dict = json.dumps(subject_object_dict, cls=DjangoJSONEncoder)
            return subject_object_dict

    def resolve_thirdparty(root, info):
        if root.thirdparty:
            # identifying fields only: the third party may be an insuree, a facility...
            thirdparty_object_dict = related_summary(root.thirdparty)
            thirdparty_object_dict = json.dumps(thirdparty_object_dict, cls=DjangoJSONEncoder)
            return thirdparty_object_dict

    class Meta:
        model = Bill
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **GenericFilterGQLTypeMixin.get_base_filters_invoice(),
            "date_bill": ["exact", "lt", "lte", "gt", "gte"],
        }

        connection_class = ExtendedConnection


class BillItemGQLType(ScopedQuerysetMixin, DjangoObjectType, GenericFilterGQLTypeMixin):
    line_type = graphene.Int()
    line_type_name = graphene.String()
    line = graphene.JSONString()

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
        model = BillItem
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **GenericFilterGQLTypeMixin.get_base_filters_invoice_line_item(),
            **prefix_filterset("bill__", BillGQLType._meta.filter_fields),
        }

        connection_class = ExtendedConnection


class BillPaymentGQLType(ScopedQuerysetMixin, DjangoObjectType, GenericFilterGQLTypeMixin):
    class Meta:
        model = BillPayment
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **GenericFilterGQLTypeMixin.get_base_filters_invoice_payment(),
            **prefix_filterset("bill__", BillGQLType._meta.filter_fields),
        }

        connection_class = ExtendedConnection


class BillEventGQLType(ScopedQuerysetMixin, DjangoObjectType, GenericFilterGQLTypeMixin):
    class Meta:
        model = BillEvent
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            **prefix_filterset("bill__", BillGQLType._meta.filter_fields),
            **GenericFilterGQLTypeMixin.get_base_filters_invoice_event(),
        }

        connection_class = ExtendedConnection
