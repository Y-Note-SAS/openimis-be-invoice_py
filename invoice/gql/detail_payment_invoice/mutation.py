import graphene
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from core.gql.gql_mutations.base_mutation import (
    BaseMutation,
    BaseHistoryModelCreateMutationMixin,
    BaseHistoryModelUpdateMutationMixin,
    BaseHistoryModelDeleteMutationMixin
)
from core.schema import OpenIMISMutation
from invoice.apps import InvoiceConfig
from invoice.gql.mutation_scope import check_in_scope, check_subject_in_scope
from invoice.models import PaymentInvoice
from invoice.gql.input_types import CreateDetailPaymentInvoiceInputType, UpdateDetailPaymentInvoiceInputType
from invoice.models import DetailPaymentInvoice, DetailPaymentInvoiceMutation


class CreateDetailPaymentInvoiceMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreateDetailPaymentInvoiceMutation"
    _mutation_module = "invoice"
    _model = DetailPaymentInvoice

    @classmethod
    def _mutate(cls, user, **data):
        client_mutation_id = data.get("client_mutation_id")
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')
        data = cls._convert_content_type(data=data)
        detail_payment_invoice = cls.create_object(user=user, object_data=data)
        if detail_payment_invoice:
            DetailPaymentInvoiceMutation.object_mutated(
                user,
                client_mutation_id=client_mutation_id,
                detail_payment_invoice=detail_payment_invoice
            )

    @classmethod
    def _convert_content_type(cls, data):
        if "subject_type" in data:
            subject_type = data.pop('subject_type')
            data['subject_type'] = ContentType.objects.get(model__iexact=subject_type)
        return data

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_payment_create_perms):
            raise ValidationError("mutation.authentication_required")
        # the payment and the invoice / bill it settles must be ones the user may see
        check_in_scope(user, PaymentInvoice, data.get('payment_id'))
        check_subject_in_scope(user, data.get('subject_type'), data.get('subject_id'))

    class Input(CreateDetailPaymentInvoiceInputType):
        pass


class UpdateDetailPaymentInvoiceMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "UpdateDetailPaymentInvoiceMutation"
    _mutation_module = "invoice"
    _model = DetailPaymentInvoice

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_payment_update_perms):
            raise ValidationError("mutation.authentication_required")
        check_in_scope(user, PaymentInvoice, data.get('payment_id'))
        check_subject_in_scope(user, data.get('subject_type'), data.get('subject_id'))

    class Input(UpdateDetailPaymentInvoiceInputType):
        pass


class DeleteDetailPaymentInvoiceMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_class = "DeleteDetailPaymentInvoiceMutation"
    _mutation_module = "invoice"
    _model = DetailPaymentInvoice

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_payment_delete_perms):
            raise ValidationError("mutation.authentication_required")

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.UUID)
