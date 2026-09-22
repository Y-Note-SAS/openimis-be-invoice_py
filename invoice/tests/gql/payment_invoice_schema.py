import uuid

from core.models import MutationLog
from invoice.models import (
    Invoice,
    InvoiceLineItem,
    PaymentInvoice,
    PaymentInvoiceMutation
)
from invoice.tests.gql.base import InvoiceGQLTestCase
from invoice.tests.helpers import (
    DEFAULT_TEST_PAYMENT_INVOICE_PAYLOAD,
    create_test_invoice,
    create_test_invoice_line_item,
    create_test_payment_invoice_with_details,
)
from django.conf import settings
from core.test_helpers import create_test_interactive_user


class PaymentInvoiceGQLTest(InvoiceGQLTestCase):

    search_for_payment_invoice_query = F'''
query {{ 
	paymentInvoice(codeTp_Iexact:"{DEFAULT_TEST_PAYMENT_INVOICE_PAYLOAD['code_tp']}", 
	amountReceived: "{DEFAULT_TEST_PAYMENT_INVOICE_PAYLOAD['amount_received']}"){{
    edges {{
      node {{
        isDeleted,
        codeTp,
        codeExt,
        amountReceived,
        datePayment,
        reconciliationStatus,
        fees,
        payerRef
      }}
    }}
  }}
}}
'''

    create_mutation_str = '''  
mutation {{
  createPaymentInvoice(input:{{reconciliationStatus: 1, codeExt:"{payment_code}", codeTp:"PAY_CODE", codeReceipt:"gqlRec", 
  label:"gql label", fees: "12.00", amountReceived: "91.50", payerRef: "payerRef", 
  datePayment:"2022-04-12", clientMutationId: "{mutation_id}"}}) {{
    internalId
    clientMutationId
  }}
}}
'''

    delete_mutation_str = '''  
mutation {{
  deletePaymentInvoice(input:{{uuids:["{payment_uuid}"], clientMutationId: "{mutation_id}"}}) {{
    internalId
    clientMutationId
  }}
}}
'''

    update_mutation_str = '''  
mutation {{
	updatePaymentInvoice(input:{{id:"{payment_uuid}", codeExt:"updExt", payerRef: "payerRef", clientMutationId: "{mutation_id}"}}){{
    internalId
    clientMutationId
  }}
}}
'''

    search_for_payment_invoice_with_detail_query = F'''
query {{ 
    paymentInvoice(codeTp_Iexact:"{DEFAULT_TEST_PAYMENT_INVOICE_PAYLOAD['code_tp']}", 
    amountReceived: "{DEFAULT_TEST_PAYMENT_INVOICE_PAYLOAD['amount_received']}"){{
    edges {{
        node {{
        isDeleted,
        codeTp,
        codeExt,
        amountReceived,
        datePayment,
        reconciliationStatus,
        fees,
        payerRef
        invoicePayments{{
          totalCount
          edges{{
            node{{
              subjectTypeName
              fees
              amount
              status
            }}
          }}
        }}
        }}
    }}
    }}
}}
'''

    search_payment_invoice_detail_query = F'''
    query {{ 
        paymentInvoice(codeTp_Iexact:"{DEFAULT_TEST_PAYMENT_INVOICE_PAYLOAD['code_tp']}", 
        amountReceived: "{DEFAULT_TEST_PAYMENT_INVOICE_PAYLOAD['amount_received']}"){{
        edges {{
            node {{
            isDeleted,
            codeTp,
            codeExt,
            amountReceived,
            datePayment,
            reconciliationStatus,
            fees,
            payerRef,
            paymentDestinationType
            paymentDestinationTypeName
            paymentDestinationId
            paymentDestination
            partyTypeName
            partyType
            partyId
            party
            invoicePayments{{
              totalCount
              edges{{
                node{{
                  subjectTypeName
                  fees
                  amount
                  status
                }}
              }}
            }}
            }}
        }}
        }}
    }}
    '''

    create_mutation_with_detail_str = '''  
mutation {{
    createPaymentWithDetailInvoice(input:{{status: 1, subjectId: "{invoice_uuid}", subjectType: "invoice",
    reconciliationStatus: 1, codeExt:"{payment_code}", codeTp:"PAY_CODE", codeReceipt:"gqlRec", 
    label:"gql label", fees: "12.00", amountReceived: "91.50", payerRef: "payerRef", 
    datePayment:"2022-04-12", clientMutationId: "{mutation_id}"}}) {{
        internalId
        clientMutationId
    }}
}}
'''
    if 'ledger' in settings.INSTALLED_APPS:
        create_mutation_with_detail_str = '''
        mutation {{
            createPaymentWithDetailInvoice(input:{{status: 1, subjectId: "{invoice_uuid}", paymentDestinationId: "{payment_destination_uuid}", partyId:"{party_uuid}", subjectType: "invoice",
            reconciliationStatus: 1, codeExt:"{payment_code}", codeTp:"PAY_CODE", codeReceipt:"gqlRec", 
            label:"gql label", fees: "12.00", amountReceived: "91.50", payerRef: "payerRef", 
            datePayment:"2022-04-12", clientMutationId: "{mutation_id}"}}) {{
                internalId
                clientMutationId
            }}
        }}
        '''
    def test_fetch_payment_invoice_query(self):
        payment_code = "GQLCOD"
        mutation_client_id = str(uuid.uuid4())
        mutation = self.create_mutation_str.format(
            payment_code=payment_code, mutation_id=mutation_client_id
        )
        self.graph_client.execute(mutation, context=self.user_context.get_request())
        output = self.graph_client.execute(self.search_for_payment_invoice_query,
                                           context=self.user_context.get_request())
        expected = \
            {'data': {
                'paymentInvoice': {
                    'edges': [
                        {'node': {
                            'isDeleted': False,
                            'codeExt': 'GQLCOD',
                            'codeTp': 'PAY_CODE',
                            'amountReceived': '91.50',
                            'datePayment': '2022-04-12',
                            'reconciliationStatus': 'A_1',
                            'fees': '12.00',
                            'payerRef': 'payerRef',
        }}]}}}
        self.assertEqual(output, expected)

    def test_fetch_payment_invoice_with_detail_query(self):
        payment = create_test_payment_invoice_with_details()
        output = self.graph_client.execute(self.search_for_payment_invoice_with_detail_query,
                                           context=self.user_context.get_request())
        expected = \
            {'data': {
                'paymentInvoice': {
                    'edges': [
                        {'node': {
                            'isDeleted': False,
                            'codeExt': payment.code_ext,
                            'codeTp': payment.code_tp,
                            'amountReceived': '91.50',
                            'datePayment': '2022-04-11',
                            'reconciliationStatus': 'A_0',
                            'fees': '12.00',
                            'payerRef': payment.payer_ref,
                            'invoicePayments': {
                                'totalCount': 1,
                                'edges': [
                                    {
                                        'node': {
                                            'subjectTypeName': 'invoice',
                                            'fees': '12.00',
                                            'amount': '91.50',
                                            'status': 'A_1'
                                        }
                                    }
                                ]
                            }
        }}]}}}
        self.assertEqual(output, expected)

    def test_create_payment_mutation(self):
        payment_code = "GQLCOD"
        mutation_client_id = str(uuid.uuid4())
        mutation = self.create_mutation_str.format(
            payment_code=payment_code, mutation_id=mutation_client_id
        )
        self.graph_client.execute(mutation, context=self.user_context.get_request())
        expected = PaymentInvoice.objects.get(code_ext=payment_code)
        mutation_log = MutationLog.objects.filter(client_mutation_id=mutation_client_id).first()
        obj = PaymentInvoiceMutation.objects.get(mutation_id=mutation_log.id).payment_invoice
        self.assertEqual(obj, expected)

    def test_create_payment_with_detail_mutation(self):
        invoice = create_test_invoice()
        invoice_item = create_test_invoice_line_item(invoice)
        payment_code = "GQLCOD"
        mutation_client_id = str(uuid.uuid4())
        if 'ledger' not in settings.INSTALLED_APPS:
            mutation = self.create_mutation_with_detail_str.format(
                payment_code=payment_code, mutation_id=mutation_client_id, invoice_uuid=invoice.id
            )
        if 'ledger' in settings.INSTALLED_APPS:
            from ledger.models import LedgerJournal, AnalyticValue, AnalyticAxis
            from hordak.models import Account
            user = create_test_interactive_user()

            cash_account = Account.objects.create(
                code="1001",
                full_code="1001",
                name="Cash",
            )
            expense_account = Account.objects.create(
                code="6001",
                full_code="6001",
                name="Expense",
            )

            payment_destination = LedgerJournal(
                code="GENERAL",
                name="General Journal",
                default_credit_account_id=cash_account,
                default_debit_account_id=expense_account,
            )
            payment_destination.save(username=user.username)

            axis = AnalyticAxis(
                code=AnalyticAxis.PARTY,
                name="Party",
            )
            axis.save(username=user.username)
            party = AnalyticValue(
                axis=axis,
                party_type=AnalyticValue.PARTY_HEALTH_FACILITY,
                external_reference="HF001",
                display_name="Health Facility 001",
            )
            party.save(username=user.username)

            mutation = self.create_mutation_with_detail_str.format(
                payment_code=payment_code, mutation_id=mutation_client_id, invoice_uuid=invoice.id,
                payment_destination_uuid=payment_destination.id, party_uuid=party.id
            )
        self.graph_client.execute(mutation, context=self.user_context.get_request())
        expected = PaymentInvoice.objects.get(code_ext=payment_code)
        mutation_log = MutationLog.objects.filter(client_mutation_id=mutation_client_id).first()
        obj = PaymentInvoiceMutation.objects.get(mutation_id=mutation_log.id).payment_invoice
        payment_invoice = PaymentInvoice.objects.filter(invoice_payments__subject_id__in=[invoice.id]).first()
        self.assertEqual(obj, expected)
        self.assertEqual(obj, payment_invoice)
        output = self.graph_client.execute(self.search_payment_invoice_detail_query,
                                                   context=self.user_context.get_request())
        InvoiceLineItem.objects.filter(id=invoice_item.id).delete()
        Invoice.objects.filter(id=invoice.id).delete()

    def test_delete_payment_mutation(self):
        payment_code = "GQLCOD"
        mutation_client_id = str(uuid.uuid4())
        mutation = self.create_mutation_str.format(
            payment_code=payment_code, mutation_id=mutation_client_id
        )
        self.graph_client.execute(mutation, context=self.user_context.get_request())
        expected = PaymentInvoice.objects.get(code_ext=payment_code)
        mutation_client_id = str(uuid.uuid4())
        mutation = self.delete_mutation_str.format(payment_uuid=expected.id, mutation_id=mutation_client_id)
        self.graph_client.execute(mutation, context=self.user_context.get_request())
        # TODO: Currently deleted entries are not filtered by manager, only in GQL Query. Should we change this?
        payment = PaymentInvoice.objects.filter(code_ext=payment_code).all()
        mutation_ = PaymentInvoiceMutation.objects.filter(payment_invoice=payment[0]).all()
        self.assertEqual(len(payment), 1)
        self.assertTrue(payment[0].is_deleted)
        self.assertTrue(len(mutation_) == 2)

    def test_update_payment_mutation(self):
        payment_code = "GQLCOD"
        mutation_client_id = str(uuid.uuid4())
        mutation = self.create_mutation_str.format(
            payment_code=payment_code, mutation_id=mutation_client_id
        )
        self.graph_client.execute(mutation, context=self.user_context.get_request())

        created = PaymentInvoice.objects.get(code_ext=payment_code)
        mutation_client_id = str(uuid.uuid4())
        mutation = self.update_mutation_str.format(payment_uuid=created.id, mutation_id=mutation_client_id)
        self.graph_client.execute(mutation, context=self.user_context.get_request())

        expected_code_ext = "updExt"
        mutation_log = MutationLog.objects.filter(client_mutation_id=mutation_client_id).first()
        obj: PaymentInvoice = PaymentInvoiceMutation.objects.get(mutation_id=mutation_log.id).payment_invoice
        self.assertEqual(obj.code_ext, expected_code_ext)
