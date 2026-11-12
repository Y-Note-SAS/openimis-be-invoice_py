"""
Security parity of invoices and bills: rows, related objects and writes stay within the
subjects the user may see (Invoice / Bill.row_scope = GenericScope("subject"), their
lines, payments and events ParentScope on them, payment details GenericScope on the
invoice / bill they settle).

Fixture: core.test_helpers.create_security_tree -> R1>D1>W1>V1 / R2>D2>W2>V2; a policy in
each village, an invoice and a bill on each policy (third party: its head insuree), with a
line, a payment and an event each, and a payment notice settling each invoice; `user_a`
holds the invoice rights globally and is assigned district D1 only.

Rows are built directly: invoice.tests.helpers sits in a package whose __init__ imports
contract / contribution_plan test helpers.
"""
import datetime
import json

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase, override_settings

from core.models.openimis_graphql_test_case import openIMISGraphQLTestCase
from core.test_helpers import create_security_tree, create_right_only_user, get_test_token, perm_ids
from insuree.test_helpers import create_test_insuree
from invoice.apps import InvoiceConfig
from invoice.models import (Bill, BillEvent, BillItem, BillPayment, DetailPaymentInvoice, Invoice, InvoiceEvent,
                            InvoiceLineItem, InvoicePayment, PaymentInvoice)
from policy.models import Policy
from policy.test_helpers import create_test_policy

INVOICE_RIGHTS = list(dict.fromkeys(
    r for name in dir(InvoiceConfig) if name.startswith("gql_") and name.endswith("_perms")
    for r in perm_ids(getattr(InvoiceConfig, name))))

#: what an invoice may tell about its subject / third party (invoice.utils)
SUMMARY_KEYS = {"id", "uuid", "code", "chfId", "name", "tradeName", "lastName", "otherNames", "runYear",
                "runMonth", "runDate", "locationId", "headInsureeId", "location", "headInsuree"}


def _product(code):
    """product.test_helpers imports program.test_helpers, absent on Cameroon's program."""
    from program.models import Program
    from product.models import Product
    program = Program.objects.create(code=code[:10], nameProgram=f"Program {code}")
    return Product.objects.create(
        code=code, name=f"Test product {code}", lump_sum=100, max_members=5,
        grace_period_enrolment=1, insurance_period=12, date_from="2019-01-01", date_to="2049-01-01",
        validity_from="2019-01-01", audit_user_id=-1, program=program)


def _decode(value):
    """the resolvers return a JSON text that the JSONString field encodes once more"""
    while isinstance(value, str):
        value = json.loads(value)
    return value


def _generic(obj):
    return ContentType.objects.get_for_model(obj), str(obj.pk)


def _build(cls, prefix):
    cls.t = create_security_tree(prefix)
    cls.user_a = create_right_only_user(f"{prefix.lower()}user", INVOICE_RIGHTS, [cls.t.d1.id])
    cls.user_norights = create_right_only_user(f"{prefix.lower()}none", [], [cls.t.d1.id])
    username = cls.user_a.username
    product = _product(f"{prefix}PR")
    for key, village in (("a", cls.t.v1), ("b", cls.t.v2)):
        insuree = create_test_insuree(
            with_family=True, is_head=True,
            custom_props={"chf_id": f"{prefix}0000{1 if key == 'a' else 2}", "current_village": village,
                          "dob": datetime.date(1980, 5, 17), "phone": "0123456789"},
            family_custom_props={"location": village})
        policy = create_test_policy(product, insuree, link=True)
        subject_type, subject_id = _generic(policy)
        thirdparty_type, thirdparty_id = _generic(insuree)
        common = dict(subject_type=subject_type, subject_id=subject_id, thirdparty_type=thirdparty_type,
                      thirdparty_id=thirdparty_id, amount_net=10, amount_total=10,
                      date_valid_from=datetime.datetime(2020, 1, 1), tax_analysis={})
        invoice = Invoice(code=f"{prefix}-INV-{key}", **common)
        invoice.save(username=username)
        bill = Bill(code=f"{prefix}-BIL-{key}", **common)
        bill.save(username=username)
        lines = dict(code=f"{prefix}-L-{key}", amount_net=10, amount_total=10, details={}, tax_analysis={},
                     date_valid_from=datetime.datetime(2020, 1, 1),
                     # a bill item ends 30 days after its batch run: still current
                     date_valid_to=datetime.datetime(2020, 2, 1))
        InvoiceLineItem(invoice=invoice, **lines).save(username=username)
        BillItem(bill=bill, **lines).save(username=username)
        payment = dict(code_tp=f"{prefix}-P-{key}", status=1, amount_payed=10)
        InvoicePayment(invoice=invoice, **payment).save(username=username)
        BillPayment(bill=bill, **payment).save(username=username)
        InvoiceEvent(invoice=invoice, message=f"{prefix}-E-{key}").save(username=username)
        BillEvent(bill=bill, message=f"{prefix}-E-{key}").save(username=username)
        notice = PaymentInvoice(code_tp=f"{prefix}-N-{key}", reconciliation_status=0, payer_ref="x",
                                amount_received=10)
        notice.save(username=username)
        detail_type, detail_id = _generic(invoice)
        DetailPaymentInvoice(payment=notice, subject_type=detail_type, subject_id=detail_id, status=1,
                             amount=10).save(username=username)
        for name, value in (("ins", insuree), ("pol", policy), ("inv", invoice), ("bill", bill),
                            ("notice", notice)):
            setattr(cls, f"{name}_{key}", value)


@override_settings(ROW_SECURITY=True)
class InvoiceReadScopeTest(openIMISGraphQLTestCase):

    @classmethod
    def setUpTestData(cls):
        _build(cls, "IVR")
        cls.token = get_test_token(cls.user_a)
        cls.token_norights = get_test_token(cls.user_norights)

    def setUp(self):
        cache.clear()

    def _q(self, query, token=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return json.loads(self.query(query, headers=headers).content)

    def _codes(self, content, field, key="code"):
        self.assertNotIn("errors", content, content.get("errors"))
        return {e["node"][key] for e in content["data"][field]["edges"]}

    def test_model_scope(self):
        for model, own, other in ((Invoice, self.inv_a, self.inv_b), (Bill, self.bill_a, self.bill_b)):
            ids = set(model.get_queryset(None, self.user_a).values_list("id", flat=True))
            self.assertIn(own.id, ids, model)
            self.assertNotIn(other.id, ids, model)
        for model, parent in ((InvoiceLineItem, "invoice"), (InvoicePayment, "invoice"), (InvoiceEvent, "invoice"),
                              (BillItem, "bill"), (BillPayment, "bill"), (BillEvent, "bill")):
            own = {"invoice": self.inv_a, "bill": self.bill_a}[parent]
            other = {"invoice": self.inv_b, "bill": self.bill_b}[parent]
            rows = model.get_queryset(model.objects.filter(**{f"{parent}__in": [own, other]}), self.user_a)
            self.assertEqual({own.id}, set(rows.values_list(f"{parent}_id", flat=True)), model)
        notices = set(PaymentInvoice.get_queryset(None, self.user_a).values_list("id", flat=True))
        self.assertIn(self.notice_a.id, notices)
        self.assertNotIn(self.notice_b.id, notices)
        details = DetailPaymentInvoice.get_queryset(
            DetailPaymentInvoice.objects.filter(payment__in=[self.notice_a, self.notice_b]), self.user_a)
        self.assertEqual({self.notice_a.id}, set(details.values_list("payment_id", flat=True)))
        self.assertFalse(Invoice.get_queryset(None, None).exists())

    def test_invoices_listed_within_the_districts(self):
        codes = self._codes(self._q('{ invoice(code_Istartswith: "IVR-") { edges { node { code } } } }',
                                    self.token), "invoice")
        self.assertEqual({"IVR-INV-a"}, codes)

    def test_bills_listed_within_the_districts(self):
        codes = self._codes(self._q('{ bill(code_Istartswith: "IVR-") { edges { node { code } } } }',
                                    self.token), "bill")
        self.assertEqual({"IVR-BIL-a"}, codes)

    def test_children_listed_within_the_districts(self):
        for field, key, value in (("invoiceLineItem", "code", "IVR-L-"), ("billItem", "code", "IVR-L-"),
                                  ("invoicePayment", "codeTp", "IVR-P-"), ("billPayment", "codeTp", "IVR-P-"),
                                  ("invoiceEvent", "message", "IVR-E-"), ("billEvent", "message", "IVR-E-"),
                                  ("paymentInvoice", "codeTp", "IVR-N-")):
            content = self._q(f'{{ {field} {{ edges {{ node {{ {key} }} }} }} }}', self.token)
            values = {v for v in self._codes(content, field, key) if v and v.startswith(value)}
            self.assertEqual({f"{value}a"}, values, field)

    def test_bill_payment_needs_a_right(self):
        content = self._q('{ billPayment { edges { node { codeTp } } } }', self.token_norights)
        self.assertTrue(content.get("errors"), content)

    def test_node_out_of_scope_not_found(self):
        from graphql_relay import to_global_id
        for type_name, obj in (("InvoiceGQLType", self.inv_b), ("BillGQLType", self.bill_b)):
            node_id = to_global_id(type_name, obj.id)
            content = self._q(f'{{ node(id: "{node_id}") {{ ... on {type_name} {{ code }} }} }}', self.token)
            self.assertIsNone((content.get("data") or {}).get("node"), content)

    def test_subject_and_thirdparty_summarised(self):
        for field in ("invoice", "bill"):
            content = self._q(f'{{ {field}(code_Istartswith: "IVR-") {{ edges {{ node {{ subject thirdparty }} }} }} }}',
                              self.token)
            self.assertNotIn("errors", content, content.get("errors"))
            node = content["data"][field]["edges"][0]["node"]
            thirdparty = _decode(node["thirdparty"])
            subject = _decode(node["subject"])
            self.assertEqual(self.ins_a.chf_id, thirdparty.get("chfId"))
            self.assertLessEqual(set(thirdparty), SUMMARY_KEYS, thirdparty)
            self.assertLessEqual(set(subject), SUMMARY_KEYS, subject)
            self.assertNotIn("dob", thirdparty)
            self.assertNotIn("phone", thirdparty)

    def test_deleted_rows_only_on_request(self):
        Invoice.objects.filter(id=self.inv_a.id).update(is_deleted=True)
        live = self._q('{ invoice(code_Istartswith: "IVR-", isDeleted: false) { edges { node { code } } } }',
                       self.token)
        self.assertEqual(set(), self._codes(live, "invoice"))
        everything = self._q('{ invoice(code_Istartswith: "IVR-") { edges { node { code } } } }', self.token)
        self.assertEqual({"IVR-INV-a"}, self._codes(everything, "invoice"))

    def test_lines_past_their_period_still_current(self):
        content = self._q('{ billItem(isDeleted: false, code_Istartswith: "IVR-") { edges { node { code } } } }',
                          self.token)
        self.assertEqual({"IVR-L-a"}, self._codes(content, "billItem"))

    def test_validity_dates_still_filter(self):
        later = self._q('{ invoice(code_Istartswith: "IVR-", dateValidTo_Lte: "2019-06-01T00:00:00") '
                        '{ edges { node { code } } } }', self.token)
        self.assertEqual(set(), self._codes(later, "invoice"))
        during = self._q('{ invoice(code_Istartswith: "IVR-", dateValidFrom_Gte: "2021-01-01T00:00:00") '
                         '{ edges { node { code } } } }', self.token)
        self.assertEqual({"IVR-INV-a"}, self._codes(during, "invoice"))


@override_settings(ROW_SECURITY=True)
class InvoiceWriteScopeTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        _build(cls, "IVW")

    def setUp(self):
        cache.clear()

    def test_delete_out_of_scope_reported_as_unknown(self):
        from invoice.gql.bill.mutation import DeleteBillMutation
        from invoice.gql.invoice.mutation import DeleteInvoiceMutation
        unknown = "00000000-0000-0000-0000-000000000001"
        for mutation, model, other in ((DeleteInvoiceMutation, Invoice, self.inv_b),
                                       (DeleteBillMutation, Bill, self.bill_b)):
            refused = mutation.async_mutate(self.user_a, uuids=[other.id])
            missing = mutation.async_mutate(self.user_a, uuids=[unknown])
            self.assertTrue(refused, model)
            self.assertEqual(missing[0]["detail"].replace(unknown, "X"),
                             refused[0]["detail"].replace(str(other.id), "X"))
            self.assertFalse(model.objects.get(id=other.id).is_deleted)

    def test_delete_in_scope_allowed(self):
        from invoice.gql.invoice.mutation import DeleteInvoiceMutation
        self.assertFalse(DeleteInvoiceMutation.async_mutate(self.user_a, uuids=[self.inv_a.id]))
        self.assertTrue(Invoice.objects.get(id=self.inv_a.id).is_deleted)

    def test_payment_on_a_bill_out_of_scope_refused(self):
        from invoice.gql.bill_payment.mutation import CreateBillPaymentMutation
        result = CreateBillPaymentMutation.async_mutate(
            self.user_a, bill_id=self.bill_b.id, code_tp="IVW-NEW", status=1, amount_payed=1)
        self.assertTrue(result)
        self.assertFalse(BillPayment.objects.filter(code_tp="IVW-NEW").exists())
        result = CreateBillPaymentMutation.async_mutate(
            self.user_a, bill_id=self.bill_a.id, code_tp="IVW-OWN", status=1, amount_payed=1)
        self.assertFalse(result)
        self.assertTrue(BillPayment.objects.filter(code_tp="IVW-OWN", bill=self.bill_a).exists())

    def test_update_payment_out_of_scope_refused(self):
        from invoice.gql.bill_payment.mutation import UpdateBillPaymentMutation
        other = BillPayment.objects.get(bill=self.bill_b)
        result = UpdateBillPaymentMutation.async_mutate(self.user_a, id=other.id, code_tp="IVW-MOVED")
        self.assertTrue(result)
        self.assertEqual("IVW-P-b", BillPayment.objects.get(id=other.id).code_tp)
        own = BillPayment.objects.get(bill=self.bill_a)
        result = UpdateBillPaymentMutation.async_mutate(self.user_a, id=own.id, bill_id=self.bill_b.id)
        self.assertTrue(result, "moved onto a bill out of scope")
        self.assertEqual(self.bill_a.id, BillPayment.objects.get(id=own.id).bill_id)

    def test_event_on_an_invoice_out_of_scope_refused(self):
        from invoice.gql.invoice_event.mutation import CreateInvoiceEventMutation
        result = CreateInvoiceEventMutation.async_mutate(self.user_a, invoice_id=self.inv_b.id, message="IVW-MSG")
        self.assertTrue(result)
        self.assertFalse(InvoiceEvent.objects.filter(message="IVW-MSG").exists())

    def test_payment_detail_on_an_invoice_out_of_scope_refused(self):
        from invoice.gql.detail_payment_invoice.mutation import CreateDetailPaymentInvoiceMutation
        result = CreateDetailPaymentInvoiceMutation.async_mutate(
            self.user_a, payment_id=self.notice_a.id, subject_type="invoice", subject_id=self.inv_b.id,
            status=1, amount=1)
        self.assertTrue(result)
        self.assertEqual(1, DetailPaymentInvoice.objects.filter(payment=self.notice_a).count())
