from datetime import date, datetime
from decimal import Decimal

from django.forms.models import model_to_dict
from django.utils import timezone

from .models import AuditLog, ChangeLog, Employee


def snapshot_instance(instance):
    if instance is None:
        return None

    data = model_to_dict(instance)
    return {
        key: _json_value(value)
        for key, value in data.items()
    }


def write_audit_log(
    request,
    action,
    event,
    obj=None,
    before=None,
    after=None,
    employee=None,
    write_change=True,
):
    actor = None
    ip_address = None
    path = ""
    if request is not None:
        if request.user.is_authenticated:
            actor = request.user
        ip_address = _client_ip(request)
        path = request.path[:255]

    log = AuditLog.objects.create(
        actor=actor,
        action=action,
        model_name=obj.__class__.__name__ if obj is not None else "",
        object_id=str(obj.pk) if obj is not None and obj.pk else "",
        object_repr=str(obj)[:255] if obj is not None else "",
        event=event[:255],
        before=before,
        after=after,
        ip_address=ip_address,
        path=path,
    )

    if write_change and employee is not None:
        ChangeLog.objects.create(
            created_at=timezone.now(),
            employee=employee,
            event=event[:255],
        )

    return log


def employee_for_object(obj):
    if isinstance(obj, Employee):
        return obj
    return getattr(obj, "employee", None)


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "pk"):
        return value.pk
    return value


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

