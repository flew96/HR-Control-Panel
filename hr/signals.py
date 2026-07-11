from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .audit import write_audit_log
from .models import AuditLog


@receiver(user_logged_in, dispatch_uid="hr.audit_successful_login")
def audit_successful_login(sender, request, user, **kwargs):
    if not hasattr(request, "user"):
        request.user = user
    write_audit_log(
        request,
        AuditLog.ACTION_LOGIN,
        "Успешный вход в систему",
        obj=user,
        after={"username": user.get_username()},
        write_change=False,
    )
