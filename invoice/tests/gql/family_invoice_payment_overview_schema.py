from datetime import date

from django.contrib.contenttypes.models import ContentType

from insuree.test_helpers import create_test_insuree
from invoice.models import DetailPaymentInvoice, PaymentInvoice
from invoice.tests.gql.base import InvoiceGQLTestCase
from invoice.tests.helpers import create_test_invoice


class FamilyInvoicePaymentOverviewGQLTest(InvoiceGQLTestCase):
    def test_family_overview_filters_invoices_for_insuree_as_thirdparty(self):
        insuree = create_test_insuree(with_family=False)
        another_insuree = create_test_insuree(with_family=False)

        insured_invoice = create_test_invoice(
            subject=insuree,
            thirdparty=insuree,
            code="INV-INSURED",
            date_invoice=date(2024, 1, 1),
            amount_total=100,
        )
        excluded_invoice = create_test_invoice(
            subject=insuree,
            thirdparty=another_insuree,
            code="INV-EXCLUDED",
            date_invoice=date(2024, 2, 1),
            amount_total=70,
        )

        payment_1 = PaymentInvoice(
            code_tp="P1",
            code_ext="REF-1",
            code_receipt="R1",
            label="Payment 1",
            reconciliation_status=PaymentInvoice.ReconciliationStatus.NOT_RECONCILIATED,
            fees=0,
            amount_received=30,
            date_payment=date(2024, 1, 10),
            payment_origin="OM",
            payer_ref="payer-1",
            payer_name="payer-1",
        )
        payment_1.save(username=self.user.username)

        payment_2 = PaymentInvoice(
            code_tp="P2",
            code_ext="REF-2",
            code_receipt="R2",
            label="Payment 2",
            reconciliation_status=PaymentInvoice.ReconciliationStatus.NOT_RECONCILIATED,
            fees=0,
            amount_received=20,
            date_payment=date(2024, 1, 15),
            payment_origin="OM",
            payer_ref="payer-2",
            payer_name="payer-2",
        )
        payment_2.save(username=self.user.username)

        excluded_payment = PaymentInvoice(
            code_tp="P3",
            code_ext="REF-3",
            code_receipt="R3",
            label="Payment 3",
            reconciliation_status=PaymentInvoice.ReconciliationStatus.NOT_RECONCILIATED,
            fees=0,
            amount_received=10,
            date_payment=date(2024, 2, 10),
            payment_origin="OM",
            payer_ref="payer-3",
            payer_name="payer-3",
        )
        excluded_payment.save(username=self.user.username)

        invoice_content_type = ContentType.objects.get_for_model(insured_invoice)

        detail_1 = DetailPaymentInvoice(
            payment=payment_1,
            subject=insured_invoice,
            subject_type=invoice_content_type,
            status=DetailPaymentInvoice.DetailPaymentStatus.ACCEPTED,
            fees=0,
            amount=30,
        )
        detail_1.save(username=self.user.username)

        detail_2 = DetailPaymentInvoice(
            payment=payment_2,
            subject=insured_invoice,
            subject_type=invoice_content_type,
            status=DetailPaymentInvoice.DetailPaymentStatus.ACCEPTED,
            fees=0,
            amount=20,
        )
        detail_2.save(username=self.user.username)

        detail_3 = DetailPaymentInvoice(
            payment=excluded_payment,
            subject=excluded_invoice,
            subject_type=invoice_content_type,
            status=DetailPaymentInvoice.DetailPaymentStatus.ACCEPTED,
            fees=0,
            amount=10,
        )
        detail_3.save(username=self.user.username)

        query = f"""
        query {{
          familyInvoicePaymentOverview(headInsureeId: \"{insuree.uuid}\", first: 10) {{
            totalCount
            totalInvoiceAmount
            totalPaidAmount
            globalBalance
            items {{
              invoiceCode
              totalInvoicePayments
              invoiceBalance
              hasInvoicePayments
            }}
          }}
        }}
        """

        output = self.graph_client.execute(query, context=self.BaseTestContext(self.user))
        overview = output["data"]["familyInvoicePaymentOverview"]
        items = overview["items"]

        self.assertEqual(overview["totalCount"], 1)
        self.assertEqual(overview["totalInvoiceAmount"], "100")
        self.assertEqual(overview["totalPaidAmount"], "50")
        self.assertEqual(overview["globalBalance"], "50")
        self.assertEqual(items[0]["invoiceCode"], "INV-INSURED")
        self.assertEqual(items[0]["totalInvoicePayments"], "50")
        self.assertEqual(items[0]["invoiceBalance"], "50")
        self.assertTrue(items[0]["hasInvoicePayments"])

    def test_invoice_payments_returns_sorted_rows_for_authorized_invoice(self):
        insuree = create_test_insuree(with_family=False)
        invoice = create_test_invoice(
            subject=insuree,
            thirdparty=insuree,
            code="INV-PAYMENTS",
            date_invoice=date(2024, 1, 1),
            amount_total=80,
        )

        payment_1 = PaymentInvoice(
            code_tp="P1",
            code_ext="REF-B",
            code_receipt="R1",
            label="Payment B",
            reconciliation_status=PaymentInvoice.ReconciliationStatus.NOT_RECONCILIATED,
            fees=0,
            amount_received=20,
            date_payment=date(2024, 1, 20),
            payment_origin="OM",
            payer_ref="payer-1",
            payer_name="payer-1",
        )
        payment_1.save(username=self.user.username)

        payment_2 = PaymentInvoice(
            code_tp="P2",
            code_ext="REF-A",
            code_receipt="R2",
            label="Payment A",
            reconciliation_status=PaymentInvoice.ReconciliationStatus.NOT_RECONCILIATED,
            fees=0,
            amount_received=15,
            date_payment=date(2024, 1, 10),
            payment_origin="OM",
            payer_ref="payer-2",
            payer_name="payer-2",
        )
        payment_2.save(username=self.user.username)

        invoice_content_type = ContentType.objects.get_for_model(invoice)

        detail_1 = DetailPaymentInvoice(
            payment=payment_1,
            subject=invoice,
            subject_type=invoice_content_type,
            status=DetailPaymentInvoice.DetailPaymentStatus.ACCEPTED,
            fees=0,
            amount=20,
        )
        detail_1.save(username=self.user.username)

        detail_2 = DetailPaymentInvoice(
            payment=payment_2,
            subject=invoice,
            subject_type=invoice_content_type,
            status=DetailPaymentInvoice.DetailPaymentStatus.ACCEPTED,
            fees=0,
            amount=15,
        )
        detail_2.save(username=self.user.username)

        query = f"""
        query {{
          invoicePayments(invoiceId: \"{invoice.id}\", headInsureeId: \"{insuree.uuid}\") {{
            paymentDate
            paymentAmount
            paymentReference
          }}
        }}
        """

        output = self.graph_client.execute(query, context=self.BaseTestContext(self.user))
        rows = output["data"]["invoicePayments"]

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["paymentDate"], "2024-01-10")
        self.assertEqual(rows[0]["paymentAmount"], "15")
        self.assertEqual(rows[0]["paymentReference"], "REF-A")
        self.assertEqual(rows[1]["paymentDate"], "2024-01-20")
        self.assertEqual(rows[1]["paymentAmount"], "20")
        self.assertEqual(rows[1]["paymentReference"], "REF-B")

    def test_invoice_payments_returns_empty_for_out_of_scope_invoice(self):
        insuree = create_test_insuree(with_family=False)
        another_insuree = create_test_insuree(with_family=False)
        excluded_invoice = create_test_invoice(
            subject=insuree,
            thirdparty=another_insuree,
            code="INV-OUT",
            date_invoice=date(2024, 1, 1),
            amount_total=60,
        )

        query = f"""
        query {{
          invoicePayments(invoiceId: \"{excluded_invoice.id}\", headInsureeId: \"{insuree.uuid}\") {{
            paymentDate
            paymentAmount
            paymentReference
          }}
        }}
        """

        output = self.graph_client.execute(query, context=self.BaseTestContext(self.user))
        self.assertEqual(output["data"]["invoicePayments"], [])
