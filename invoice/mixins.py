from django.conf import settings
from django.db import models

from core.models import HistoryModelManager, Validity


class GenericInvoiceManager(HistoryModelManager):
    def filter(self, *args, **kwargs):
        keys = [x for x in kwargs if "itemsvc" in x]
        for key in keys:
            new_key = key.replace("itemsvc", self.model.model_prefix)
            kwargs[new_key] = kwargs.pop(key)
        return super(GenericInvoiceManager, self).filter(*args, **kwargs)


class GenericInvoiceQuerysetMixin:
    """
    Row security of the invoice models: the model's `row_scope` (GenericScope on the
    subject of an invoice / bill, ParentScope on the invoice / bill of a line, payment or
    event), nothing to see for an anonymous user. Validity / audits (OP-2029) when asked
    for, the model's filter_queryset otherwise.
    """

    @classmethod
    def validity_q(cls, validity):
        """
        An invoice / bill and its rows stay current until deleted: their validity dates
        are the period they bill (a bill item ends 30 days after its batch run), not the
        life of the row. A validity date / range still reads those dates.
        """
        if validity == Validity.NOW:
            return cls.live_rows_q()
        return super().validity_q(validity)

    @classmethod
    def get_queryset(cls, queryset, user=None, *, validity=None, audits=None):
        queryset = cls.apply_row_filters(queryset, validity, audits, default=cls.filter_queryset)
        user = cls.scoping_user(user)
        if settings.ROW_SECURITY and (user is None or getattr(user, "is_anonymous", True)):
            return queryset.none()
        if not settings.ROW_SECURITY or cls.row_scope is None:
            return queryset
        return cls.row_scope.filter(queryset, user, cls)
