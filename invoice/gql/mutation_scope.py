"""
The rows a create / update mutation attaches its row to (the invoice or bill of a
payment or an event, the payment and the subject of a payment detail) must be rows the
user may see: one out of their scope is reported exactly like an unknown one.

The rows updated / deleted themselves are looked up by core's base mutations through
`target_queryset`, i.e. the model's row scope.
"""
from django.contrib.contenttypes.models import ContentType

from core.gql.gql_mutations import ObjectNotExistException
from core.models.row_security import target_queryset


def check_in_scope(user, model, pk):
    """Refuse `pk` of `model` unless `user` may see it; no pk, nothing to check."""
    if pk is None:
        return
    if not target_queryset(model, user).filter(id=pk).exists():
        raise ObjectNotExistException(model, pk)


def check_subject_in_scope(user, subject_type, subject_id):
    """The generic subject (`subject_type` a content type model name, or a ContentType)."""
    if subject_type is None or subject_id is None:
        return
    content_type = subject_type if isinstance(subject_type, ContentType) \
        else ContentType.objects.filter(model__iexact=subject_type).first()
    model = content_type.model_class() if content_type else None
    if model is None or not target_queryset(model, user).filter(pk=subject_id).exists():
        raise ObjectNotExistException(subject_type, subject_id)
