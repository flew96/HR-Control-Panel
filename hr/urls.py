from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("employees/", views.employees_list, name="employees_list"),
    path("employees/export/", views.employees_export, name="employees_export"),
    path("employees/import/", views.employees_import, name="employees_import"),
    path("employees/import/template/", views.employees_import_template, name="employees_import_template"),
    path("employees/columns/", views.employee_columns_update, name="employee_columns_update"),
    path("employees/new/", views.employee_create, name="employee_create"),
    path("employees/<int:pk>/", views.employee_detail, name="employee_detail"),
    path("employees/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
    path("employees/<int:pk>/terminate/", views.employee_terminate, name="employee_terminate"),
    path("employees/<int:pk>/restore/", views.employee_restore, name="employee_restore"),
    path("probation/", views.probation_list, name="probation_list"),
    path("probation/<int:pk>/toggle/<str:field>/", views.probation_toggle_stage, name="probation_toggle_stage"),
    path("probation/<int:pk>/result/", views.probation_set_result, name="probation_set_result"),
    path("departments/", views.departments_list, name="departments_list"),
    path("departments/export/", views.departments_export, name="departments_export"),
    path("departments/new/", views.department_create, name="department_create"),
    path("departments/<int:pk>/edit/", views.department_edit, name="department_edit"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("campaigns/", views.campaigns_list, name="campaigns_list"),
    path("campaigns/new/", views.campaign_create, name="campaign_create"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="campaign_detail"),
    path("campaigns/<int:pk>/records/add/", views.campaign_record_add, name="campaign_record_add"),
    path("guide/", views.simple_page, {"page": "guide"}, name="guide"),
    path("positions/", views.simple_page, {"page": "positions"}, name="positions"),
    path("mail-templates/", views.simple_page, {"page": "mail_templates"}, name="mail_templates"),
    path("users/", views.simple_page, {"page": "users"}, name="users"),
    path("data-audit/", views.simple_page, {"page": "data_audit"}, name="data_audit"),
    path("action-log/", views.simple_page, {"page": "action_log"}, name="action_log"),
]
