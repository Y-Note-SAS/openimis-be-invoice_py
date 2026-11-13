"""
invoice_row_filters (legacy validity arguments as the model's validity) and
related_summary (the identifying fields of a subject), PR Y-Note-SAS#55 review.
"""
import datetime as py_datetime
from types import SimpleNamespace

from django.core.exceptions import ObjectDoesNotExist
from django.test import SimpleTestCase

from core.models import Validity
from invoice.gql.row_filters import invoice_row_filters
from invoice.models import Bill, BillEvent
from invoice.utils import related_summary


def _info():
    return SimpleNamespace(context=SimpleNamespace())


class InvoiceRowFiltersTest(SimpleTestCase):
    start = py_datetime.datetime(2024, 1, 1)
    end = py_datetime.datetime(2024, 12, 31)

    def test_both_dates_give_the_overlapping_business_validity(self):
        rows = invoice_row_filters(_info(), {"dateValidFrom__Gte": self.start, "dateValidTo__Lte": self.end}, Bill)
        self.assertEqual(Validity.between(self.start, self.end), rows["validity"])

    def test_end_only_starts_at_the_earlier_of_today_and_the_end(self):
        rows = invoice_row_filters(_info(), {"dateValidTo__Lte": self.end}, Bill)
        self.assertEqual(Validity.between(self.end, self.end), rows["validity"])

    def test_default_validity_filter_is_still_valid_from_now(self):
        rows = invoice_row_filters(_info(), {"applyDefaultValidityFilter": True}, Bill)
        self.assertEqual("between", rows["validity"].kind)
        self.assertIsNone(rows["validity"].end)

    def test_default_validity_filter_without_business_dates_is_now(self):
        rows = invoice_row_filters(_info(), {"applyDefaultValidityFilter": True}, BillEvent)
        self.assertEqual(Validity.NOW, rows["validity"])

    def test_no_argument_is_every_row(self):
        rows = invoice_row_filters(_info(), {}, Bill)
        self.assertEqual(Validity.ALL, rows["validity"])

    def test_explicit_is_deleted_wins(self):
        rows = invoice_row_filters(_info(), {"isDeleted": False}, Bill)
        self.assertEqual(Validity.NOW, rows["validity"])

    def test_recorded_on_the_context(self):
        """the contract the resolvers rely on: no return value to add to their filters"""
        info = _info()
        invoice_row_filters(info, {}, Bill)
        self.assertTrue(vars(info.context), "nothing recorded on info.context")
        self.assertIn(Validity.ALL, [v for d in vars(info.context).values() if isinstance(d, dict)
                                     for v in d.values()])


class RelatedSummaryTest(SimpleTestCase):

    def test_identifying_fields_only_in_camel_case(self):
        subject = SimpleNamespace(id=7, chf_id="X1", last_name="Doe", head_insuree_id=3,
                                  dob="1990-01-01", phone="+237")
        self.assertEqual({"id": 7, "chfId": "X1", "lastName": "Doe", "headInsureeId": 3},
                         related_summary(subject))

    def test_missing_relation_is_left_out(self):
        class Subject:
            id = 1

            @property
            def location_id(self):
                raise ObjectDoesNotExist("no location")
        self.assertEqual({"id": 1}, related_summary(Subject()))

    def test_methods_are_left_out(self):
        subject = SimpleNamespace(id=1, name=lambda: "x")
        self.assertEqual({"id": 1}, related_summary(subject))

    def test_none(self):
        self.assertIsNone(related_summary(None))

    def test_unexpected_error_is_not_hidden(self):
        class Subject:
            @property
            def id(self):
                raise ValueError("bug in a getter")
        with self.assertRaises(ValueError):
            related_summary(Subject())
