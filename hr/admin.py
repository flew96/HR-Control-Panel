from django.contrib import admin

from .models import (
    Campaign,
    CampaignRecord,
    AuditLog,
    ChangeLog,
    Contract,
    Department,
    EmployeeColumnPreference,
    Employee,
    Position,
    Probation,
)


admin.site.register(Department)
admin.site.register(Position)
admin.site.register(Employee)
admin.site.register(Probation)
admin.site.register(Campaign)
admin.site.register(CampaignRecord)
admin.site.register(Contract)
admin.site.register(ChangeLog)
admin.site.register(AuditLog)
admin.site.register(EmployeeColumnPreference)
