from core import datetime
from core.gql import legacy_row_filters
from core.models import Validity


def invoice_row_filters(info, kwargs, model):
    """
    The legacy validity arguments of the invoice connections (core.utils.
    append_validity_filter) as the validity applied by `model.get_queryset` (OP-2029):

    - dateValidFrom__Gte / dateValidTo__Lte: the rows whose business validity overlaps
      them (a missing start is the earlier of today and the end);
    - applyDefaultValidityFilter: the rows still valid from now on;
    - neither: every row, deleted ones included (an explicit isDeleted narrows it).

    The resolver no longer filters validity itself.
    """
    date_from = kwargs.get('dateValidFrom__Gte')
    date_to = kwargs.get('dateValidTo__Lte')
    business = bool(model.get_business_validity_fields())
    if business and (date_from or date_to):
        start = date_from or min(datetime.datetime.now(), date_to)
        validity = Validity.between(start, date_to)
    elif kwargs.get('applyDefaultValidityFilter'):
        validity = Validity.between(datetime.datetime.now(), None) if business else Validity.NOW
    else:
        validity = Validity.ALL
    return legacy_row_filters(info, kwargs, validity=validity)
