import graphene
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from core.gql.gql_mutations.base_mutation import BaseMutation, BaseCreateMutationMixin, BaseUpdateMutationMixin, \
    BaseHistoryModelCreateMutationMixin, BaseHistoryModelUpdateMutationMixin, BaseHistoryModelDeleteMutationMixin
from core.schema import OpenIMISMutation
from invoice.apps import InvoiceConfig
from invoice.gql.mutation_scope import check_in_scope
from invoice.models import Bill
from invoice.gql.input_types import CreateBillPaymentInputType, UpdateBillPaymentInputType
from invoice.models import BillPayment, BillPaymentMutation


class CreateBillPaymentMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreateBillPaymentMutation"
    _mutation_module = "invoice"
    _model = BillPayment

    @classmethod
    def _mutate(cls, user, **data):
        client_mutation_id = data.get("client_mutation_id")
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')
        p = cls.create_object(user=user, object_data=data)
        if p:
            BillPaymentMutation.object_mutated(
                user,
                client_mutation_id=client_mutation_id,
                bill_payment=p
            )

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_bill_payment_create_perms):
            raise ValidationError("mutation.authentication_required")
        # the bill paid must be one the user may see
        check_in_scope(user, Bill, data.get('bill_id'))

    class Input(CreateBillPaymentInputType):
        pass


class UpdateBillPaymentMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "UpdateBillPaymentMutation"
    _mutation_module = "invoice"
    _model = BillPayment

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_bill_payment_update_perms):
            raise ValidationError("mutation.authentication_required")
        check_in_scope(user, Bill, data.get('bill_id'))

    class Input(UpdateBillPaymentInputType):
        pass


class DeleteBillPaymentMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_class = "DeleteBillPaymentMutation"
    _mutation_module = "invoice"
    _model = BillPayment

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_bill_payment_delete_perms):
            raise ValidationError("mutation.authentication_required")

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.UUID)
