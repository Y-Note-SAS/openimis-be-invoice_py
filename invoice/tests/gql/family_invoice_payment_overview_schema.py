import uuid
from datetime import date, datetime, timezone as dt_timezone

from core.models.openimis_graphql_test_case import BaseTestContext
from core.test_helpers import create_test_interactive_user
from insuree.test_helpers import create_test_insuree

from invoice.tests.gql.base import InvoiceGQLTestCase
from invoice.tests.helpers import create_test_invoice, create_test_payment_invoice_with_details


OVERVIEW_QUERY = """
query {
  familyInvoicePaymentOverview(headInsureeId: "%s"%s) {
    totalCount
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
    items {
      rowId
      invoiceId
      invoiceCode
      coveredFrom
      coveredTo
      amountDue
      totalInvoicePayments
      invoiceBalance
      lastPayment
      hasInvoicePayments
    }
  }
}
"""

GLOBALS_QUERY = """
query {
  familyInvoicePaymentGlobals(headInsureeId: "%s") {
    totalInvoiceAmount
    totalPaidAmount
    globalBalance
  }
}
"""


class FamilyInvoicePaymentOverviewGQLTest(InvoiceGQLTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.first_invoice = create_test_invoice(
            subject=cls.insuree,
            thirdparty=cls.insuree,
            user=cls.user,
            code="FAMILY_OVERVIEW_INVOICE_1",
            amount_total="100.00",
            date_invoice=date(2021, 1, 10),
            date_valid_from=datetime(2021, 1, 1, tzinfo=dt_timezone.utc),
            date_valid_to=datetime(2021, 6, 30, tzinfo=dt_timezone.utc),
        )
        cls.second_invoice = create_test_invoice(
            subject=cls.insuree,
            thirdparty=cls.insuree,
            user=cls.user,
            code="FAMILY_OVERVIEW_INVOICE_2",
            amount_total="50.00",
            date_invoice=date(2021, 2, 10),
            date_valid_from=datetime(2021, 2, 1, tzinfo=dt_timezone.utc),
            date_valid_to=datetime(2021, 7, 31, tzinfo=dt_timezone.utc),
        )
        # Invoice charged to another insuree: it must never show up in the family overview.
        cls.other_insuree = create_test_insuree(with_family=True)
        cls.other_invoice = create_test_invoice(
            subject=cls.other_insuree,
            thirdparty=cls.other_insuree,
            user=cls.user,
            code="FAMILY_OVERVIEW_INVOICE_OTHER",
            amount_total="30.00",
            date_invoice=date(2021, 3, 10),
        )
        # Invoice on the family insuree but charged to a third party (e.g. AFD/government),
        # with its own payment: it must be excluded from both the list and the totals.
        cls.third_party_invoice = create_test_invoice(
            subject=cls.insuree,
            thirdparty=cls.other_insuree,
            user=cls.user,
            code="FAMILY_OVERVIEW_INVOICE_THIRD_PARTY",
            amount_total="70.00",
            date_invoice=date(2021, 4, 10),
        )
        create_test_payment_invoice_with_details(invoice=cls.first_invoice, user=cls.user)
        create_test_payment_invoice_with_details(invoice=cls.third_party_invoice, user=cls.user)
        cls.user_without_rights = create_test_interactive_user(
            username="family_overview_no_rights",
            roles=[],
            custom_props={"is_superuser": False},
        )

    def test_family_invoice_payment_overview_returns_the_family_invoices(self):
        output = self.graph_client.execute(
            OVERVIEW_QUERY % (self.insuree.uuid, ""), context=self.user_context.get_request()
        )

        expected = {
            "data": {
                "familyInvoicePaymentOverview": {
                    "totalCount": 2,
                    "pageInfo": {
                        "hasNextPage": False,
                        "hasPreviousPage": False,
                        "startCursor": "Y3Vyc29yOjA=",
                        "endCursor": "Y3Vyc29yOjE=",
                    },
                    "items": [
                        {
                            "rowId": f"invoice-{self.first_invoice.id}",
                            "invoiceId": str(self.first_invoice.id),
                            "invoiceCode": "FAMILY_OVERVIEW_INVOICE_1",
                            "coveredFrom": "2021-01-01",
                            "coveredTo": "2021-06-30",
                            "amountDue": "100.00",
                            "totalInvoicePayments": "91.50",
                            "invoiceBalance": "8.50",
                            "lastPayment": "2022-04-11",
                            "hasInvoicePayments": True,
                        },
                        {
                            "rowId": f"invoice-{self.second_invoice.id}",
                            "invoiceId": str(self.second_invoice.id),
                            "invoiceCode": "FAMILY_OVERVIEW_INVOICE_2",
                            "coveredFrom": "2021-02-01",
                            "coveredTo": "2021-07-31",
                            "amountDue": "50.00",
                            "totalInvoicePayments": "0",
                            "invoiceBalance": "50.00",
                            "lastPayment": None,
                            "hasInvoicePayments": False,
                        },
                    ],
                }
            }
        }

        self.assertEqual(output, expected)

    def test_family_invoice_payment_overview_paginates_with_cursors(self):
        first_page = self.graph_client.execute(
            OVERVIEW_QUERY % (self.insuree.uuid, ", first: 1"), context=self.user_context.get_request()
        )
        first_page_node = first_page["data"]["familyInvoicePaymentOverview"]
        second_page = self.graph_client.execute(
            OVERVIEW_QUERY % (self.insuree.uuid, f', first: 1, after: "{first_page_node["pageInfo"]["endCursor"]}"'),
            context=self.user_context.get_request(),
        )
        second_page_node = second_page["data"]["familyInvoicePaymentOverview"]

        self.assertEqual(first_page_node["totalCount"], 2)
        self.assertEqual(
            first_page_node["pageInfo"],
            {
                "hasNextPage": True,
                "hasPreviousPage": False,
                "startCursor": "Y3Vyc29yOjA=",
                "endCursor": "Y3Vyc29yOjA=",
            },
        )
        self.assertEqual(
            [item["invoiceCode"] for item in first_page_node["items"]],
            ["FAMILY_OVERVIEW_INVOICE_1"],
        )
        self.assertEqual(second_page_node["totalCount"], 2)
        self.assertEqual(
            second_page_node["pageInfo"],
            {
                "hasNextPage": False,
                "hasPreviousPage": True,
                "startCursor": "Y3Vyc29yOjE=",
                "endCursor": "Y3Vyc29yOjE=",
            },
        )
        self.assertEqual(
            [item["invoiceCode"] for item in second_page_node["items"]],
            ["FAMILY_OVERVIEW_INVOICE_2"],
        )

    def test_family_invoice_payment_overview_excludes_invoices_charged_to_a_third_party(self):
        overview = self.graph_client.execute(
            OVERVIEW_QUERY % (self.insuree.uuid, ""), context=self.user_context.get_request()
        )["data"]["familyInvoicePaymentOverview"]
        globals_ = self.graph_client.execute(
            GLOBALS_QUERY % self.insuree.uuid, context=self.user_context.get_request()
        )["data"]["familyInvoicePaymentGlobals"]

        self.assertEqual(
            [item["invoiceCode"] for item in overview["items"]],
            ["FAMILY_OVERVIEW_INVOICE_1", "FAMILY_OVERVIEW_INVOICE_2"],
        )
        self.assertEqual(overview["totalCount"], 2)
        self.assertEqual(
            globals_,
            {
                "totalInvoiceAmount": "150.00",
                "totalPaidAmount": "91.50",
                "globalBalance": "58.50",
            },
        )

    def test_family_invoice_payment_globals_aggregates_the_family_invoices(self):
        output = self.graph_client.execute(GLOBALS_QUERY % self.insuree.uuid, context=self.user_context.get_request())

        expected = {
            "data": {
                "familyInvoicePaymentGlobals": {
                    "totalInvoiceAmount": "150.00",
                    "totalPaidAmount": "91.50",
                    "globalBalance": "58.50",
                }
            }
        }

        self.assertEqual(output, expected)

    def test_family_invoice_payment_overview_is_empty_for_an_unknown_family(self):
        output = self.graph_client.execute(
            OVERVIEW_QUERY % (uuid.uuid4(), ""), context=self.user_context.get_request()
        )

        expected = {
            "data": {
                "familyInvoicePaymentOverview": {
                    "totalCount": 0,
                    "pageInfo": {
                        "hasNextPage": False,
                        "hasPreviousPage": False,
                        "startCursor": None,
                        "endCursor": None,
                    },
                    "items": [],
                }
            }
        }

        self.assertEqual(output, expected)

    def test_family_invoice_payment_queries_reject_a_user_without_invoice_search_rights(self):
        context = BaseTestContext(self.user_without_rights).get_request()

        for query, field in (
            (OVERVIEW_QUERY % (self.insuree.uuid, ""), "familyInvoicePaymentOverview"),
            (GLOBALS_QUERY % self.insuree.uuid, "familyInvoicePaymentGlobals"),
        ):
            output = self.graph_client.execute(query, context=context)

            expected = {
                "errors": [
                    {
                        "message": "Unauthorized",
                        "locations": [{"line": 3, "column": 3}],
                        "path": [field],
                    }
                ],
                "data": {field: None},
            }

            self.assertEqual(output, expected)
