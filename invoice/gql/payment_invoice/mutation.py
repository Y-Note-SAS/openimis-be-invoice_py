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
from invoice.gql.input_types import (
    CreatePaymentInvoiceInputType,
    CreatePaymentInvoiceWithDetailInputType,
    UpdatePaymentInvoiceInputType
)
from invoice.models import (
    PaymentInvoice,
    PaymentInvoiceMutation,
    DetailPaymentInvoice
)
from im_export.services import BankImportService
from invoice.models import Invoice
from insuree.models import Insuree

class CreatePaymentInvoiceMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreatePaymentInvoiceMutation"
    _mutation_module = "invoice"
    _model = PaymentInvoice

    @classmethod
    def _mutate(cls, user, **data):
        client_mutation_id = data.get("client_mutation_id")
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')
        payment_invoice = cls.create_object(user=user, object_data=data)
        if payment_invoice:
            PaymentInvoiceMutation.object_mutated(
                user,
                client_mutation_id=client_mutation_id,
                payment_invoice=payment_invoice
            )

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_payment_create_perms):
            raise ValidationError("mutation.authentication_required")

    class Input(CreatePaymentInvoiceInputType):
        pass


class CreatePaymentInvoiceWithDetailMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreatePaymentInvoiceWithDetailMutation"
    _mutation_module = "invoice"
    _model = PaymentInvoice

    @classmethod
    def _mutate(cls, user, **data):
        client_mutation_id = data.get("client_mutation_id")
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')
        status, subject_id, subject_type = cls._get_field_for_detail(data)
        payment_invoice = cls.create_object(user=user, object_data=data)
        if payment_invoice:
            PaymentInvoiceMutation.object_mutated(
                user,
                client_mutation_id=client_mutation_id,
                payment_invoice=payment_invoice
            )
            cls._create_payment_detail(user, data, payment_invoice, status, subject_id, subject_type)
            
            invoice = Invoice.objects.get(uuid=subject_id)
            insuree = Insuree.objects.get(id=invoice.thirdparty_id)
            chf_id = insuree.chf_id

            if chf_id:
                service = BankImportService(user.i_user)
                service.create_premium(chf_id, payment_invoice)

    @classmethod
    def _get_field_for_detail(cls, data):
        status = data.pop('status')
        subject_id = data.pop('subject_id')
        subject_type = data.pop('subject_type')
        return status, subject_id, subject_type

    @classmethod
    def _create_payment_detail(cls, user, data, payment, status, subject_id, subject_type):
        payment_detail = cls._build_payment_detail(data, payment, status, subject_id, subject_type)
        detail_payment_invoice = DetailPaymentInvoice(**payment_detail)
        detail_payment_invoice.save(username=user.username)

    @classmethod
    def _build_payment_detail(cls, data, payment, status, subject_id, subject_type):
        return {
            "status": status,
            "payment_id": payment.id,
            "subject_type": cls._convert_content_type(subject_type),
            "subject_id": subject_id,
            "fees": data['fees'],
            "amount": data['amount_received'],
        }

    @classmethod
    def _convert_content_type(cls, subject_type):
        return ContentType.objects.get(model__iexact=subject_type)

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_payment_create_perms):
            raise ValidationError("mutation.authentication_required")

    class Input(CreatePaymentInvoiceWithDetailInputType):
        pass


class UpdatePaymentInvoiceMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "UpdatePaymentInvoiceMutation"
    _mutation_module = "invoice"
    _model = PaymentInvoice

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_payment_update_perms):
            raise ValidationError("mutation.authentication_required")

    class Input(UpdatePaymentInvoiceInputType):
        pass


class DeletePaymentInvoiceMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_class = "DeletePaymentInvoiceMutation"
    _mutation_module = "invoice"
    _model = PaymentInvoice

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                InvoiceConfig.gql_invoice_payment_delete_perms):
            raise ValidationError("mutation.authentication_required")

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.UUID)
