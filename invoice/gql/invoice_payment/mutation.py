import graphene
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from core.gql.gql_mutations.base_mutation import BaseMutation, BaseCreateMutationMixin, BaseUpdateMutationMixin, \
    BaseHistoryModelCreateMutationMixin, BaseHistoryModelUpdateMutationMixin, BaseHistoryModelDeleteMutationMixin
from core.schema import OpenIMISMutation
from invoice.apps import InvoiceConfig
from invoice.gql.mutation_scope import check_in_scope
from invoice.models import Invoice
from invoice.gql.input_types import CreatePaymentInputType, UpdatePaymentInputType
from invoice.models import InvoicePayment, InvoicePaymentMutation


class CreateInvoicePaymentMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreateInvoicePaymentMutation"
    _mutation_module = "invoice"
    _model = InvoicePayment

    @classmethod
    def _mutate(cls, user, **data):
        client_mutation_id = data.get("client_mutation_id")
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')
        p = cls.create_object(user=user, object_data=data)
        if p:
            InvoicePaymentMutation.object_mutated(
                user,
                client_mutation_id=client_mutation_id,
                invoice_payment=p
            )

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_payment_create_perms):
            raise ValidationError("mutation.authentication_required")
        # the invoice paid must be one the user may see
        check_in_scope(user, Invoice, data.get('invoice_id'))

    class Input(CreatePaymentInputType):
        pass


class UpdateInvoicePaymentMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "UpdateInvoicePaymentMutation"
    _mutation_module = "invoice"
    _model = InvoicePayment

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_update_perms):
            raise ValidationError("mutation.authentication_required")
        check_in_scope(user, Invoice, data.get('invoice_id'))

    class Input(UpdatePaymentInputType):
        pass


class DeleteInvoicePaymentMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_class = "DeleteInvoicePaymentMutation"
    _mutation_module = "invoice"
    _model = InvoicePayment

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_delete_perms):
            raise ValidationError("mutation.authentication_required")

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.UUID)
