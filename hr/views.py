import csv
from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import (
    scoped_employee_queryset,
    user_can_access_employee,
    user_has_global_employee_scope,
)
from .audit import audit_logs_with_diffs, snapshot_instance, write_audit_log
from .columns import (
    EMPLOYEE_COLUMNS,
    PAGE_SIZE_CHOICES,
    get_employee_column_preference,
    save_employee_column_preference,
)
from .excel import (
    apply_employee_import_rows,
    build_employee_workbook,
    preview_employees_from_xlsx,
)
from .forms import (
    CampaignForm,
    CampaignRecordForm,
    DepartmentForm,
    EmailTemplateForm,
    EmployeeForm,
    PositionForm,
    ReferenceItemForm,
)
from .models import (
    AuditLog,
    Campaign,
    CampaignRecord,
    Contract,
    Department,
    EmailTemplate,
    Employee,
    Position,
    Probation,
    ReferenceItem,
)


MONTHS_RU = [
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

CALENDAR_EVENT_TYPES = {
    "hire": "Приёмы",
    "dismissal": "Увольнения",
    "probation": "Испытательный срок",
    "ipr": "ИПР",
    "campaign": "Кампании",
}

PROBATION_STAGE_FIELDS = {
    "week_1_done": ("1 неделя", 7),
    "month_1_done": ("1 месяц", 30),
    "middle_review_done": ("Промежуточная оценка", 45),
    "month_2_done": ("2 месяца", 60),
    "final_review_done": ("Финальная оценка", None),
    "final_survey_done": ("Финальный опрос", None),
}

SIMPLE_PAGES = {
    "guide": {
        "title": "Руководство",
        "description": "Быстрый старт, роли и безопасная работа с HR-данными.",
    },
    "positions": {
        "title": "Должности",
        "description": "Справочник должностей, используемый в карточках сотрудников.",
    },
    "mail_templates": {
        "title": "Шаблоны писем",
        "description": "Заготовка под шаблоны email-уведомлений.",
    },
    "users": {
        "title": "Пользователи",
        "description": "Пользователи системы, группы и активность.",
    },
    "data_audit": {
        "title": "Аудит-лог данных",
        "description": "Изменения HR-сущностей: кто, когда и какие поля поменял.",
    },
    "action_log": {
        "title": "Журнал действий",
        "description": "Системные операции: входы, импорты, экспорты и служебные действия.",
    },
}

REFERENCE_DIRECTORY_CONFIG = {
    "contract-types": {
        "category": ReferenceItem.CATEGORY_CONTRACT_TYPE,
        "title": "Типы договоров",
        "description": "Справочник типов договоров для HR-операций.",
    },
    "dismissal-reasons": {
        "category": ReferenceItem.CATEGORY_DISMISSAL_REASON,
        "title": "Причины увольнения",
        "description": "Справочник причин увольнения для карточек сотрудников.",
    },
    "calendar-event-types": {
        "category": ReferenceItem.CATEGORY_CALENDAR_EVENT_TYPE,
        "title": "Типы событий календаря",
        "description": "Справочник типов событий для будущего расширения календаря.",
    },
}


def _querystring_without(request, *excluded_keys):
    params = request.GET.copy()
    for key in excluded_keys:
        params.pop(key, None)
    return params.urlencode()


def _employee_queryset(request):
    return scoped_employee_queryset(
        request.user,
        Employee.objects.select_related("department", "position", "manager", "dismissal_reason"),
    )


@login_required
@permission_required("hr.view_employee", raise_exception=True)
def dashboard(request):
    today = timezone.localdate()
    soon = today + timedelta(days=30)
    visible_employee_ids = _employee_queryset(request).values("id")

    expiring_contracts = (
        Contract.objects.select_related("employee")
        .filter(
            employee_id__in=visible_employee_ids,
            employee__is_active=True,
            end_date__gte=today,
            end_date__lte=soon,
        )
        .order_by("end_date")[:10]
    )
    contract_rows = [
        {
            "contract": contract,
            "days_left": (contract.end_date - today).days if contract.end_date else None,
        }
        for contract in expiring_contracts
    ]

    stats = [
        {
            "label": "Активные сотрудники",
            "value": _employee_queryset(request).filter(is_active=True).count(),
            "accent": "blue",
        },
        {
            "label": "Устаревшие ИПР",
            "value": _employee_queryset(request).filter(ipr_status=Employee.IPR_EXPIRED).count(),
            "accent": "red",
        },
        {
            "label": "ИПР истекает за 30 дней",
            "value": _employee_queryset(request).filter(ipr_status=Employee.IPR_EXPIRING).count(),
            "accent": "amber",
        },
        {
            "label": "Открытые кампании",
            "value": Campaign.objects.filter(
                status=Campaign.STATUS_OPEN,
                records__employee_id__in=visible_employee_ids,
            ).distinct().count(),
            "accent": "green",
        },
        {
            "label": "Активные записи кампаний",
            "value": CampaignRecord.objects.filter(
                campaign__status=Campaign.STATUS_OPEN,
                status=CampaignRecord.STATUS_ACTIVE,
                employee_id__in=visible_employee_ids,
            ).count(),
            "accent": "violet",
        },
    ]

    recent_changes = AuditLog.objects.select_related("actor")
    if not user_has_global_employee_scope(request.user):
        recent_changes = recent_changes.filter(
            model_name="Employee",
            object_id__in=[str(pk) for pk in visible_employee_ids.values_list("id", flat=True)],
        )
    recent_changes = recent_changes.order_by("-created_at")[:8]

    return render(
        request,
        "hr/dashboard.html",
        {
            "stats": stats,
            "contract_rows": contract_rows,
            "recent_changes": recent_changes,
        },
    )


def _filtered_employees(request):
    employees = _employee_queryset(request)

    if request.GET.get("show_inactive") != "1":
        employees = employees.filter(is_active=True)

    query = request.GET.get("q", "").strip()
    if query:
        employees = employees.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(middle_name__icontains=query)
            | Q(email__icontains=query)
        )

    department_id = request.GET.get("department")
    if department_id:
        employees = employees.filter(department_id=department_id)

    position_id = request.GET.get("position")
    if position_id:
        employees = employees.filter(position_id=position_id)

    ipr_status = request.GET.get("ipr_status")
    if ipr_status:
        employees = employees.filter(ipr_status=ipr_status)

    return employees.order_by("last_name", "first_name", "middle_name")


@login_required
@permission_required("hr.view_employee", raise_exception=True)
def employees_list(request):
    filtered_employees = _filtered_employees(request)
    total_count = filtered_employees.count()
    missing_salary_count = filtered_employees.filter(
        Q(salary_gross__isnull=True) | Q(salary_net__isnull=True)
    ).count()
    payroll_by_currency = list(
        filtered_employees.values("currency")
        .annotate(
            employees_count=Count("id"),
            gross_total=Sum("salary_gross"),
            net_total=Sum("salary_net"),
            gross_avg=Avg("salary_gross"),
            net_avg=Avg("salary_net"),
        )
        .order_by("currency")
    )

    visible_columns, page_size = get_employee_column_preference(request.user)
    paginator = Paginator(filtered_employees, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "hr/employees/list.html",
        {
            "employees": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "departments": Department.objects.order_by("name"),
            "positions": Position.objects.order_by("name"),
            "ipr_status_choices": Employee.IPR_STATUS_CHOICES,
            "column_options": EMPLOYEE_COLUMNS,
            "visible_columns": visible_columns,
            "visible_column_count": len(visible_columns),
            "page_size": page_size,
            "page_size_choices": PAGE_SIZE_CHOICES,
            "query_string": _querystring_without(request, "page"),
            "payroll_by_currency": payroll_by_currency,
            "summary": {
                "count": total_count,
                "missing_salary_count": missing_salary_count,
            },
            "filters": {
                "q": request.GET.get("q", ""),
                "department": request.GET.get("department", ""),
                "position": request.GET.get("position", ""),
                "ipr_status": request.GET.get("ipr_status", ""),
                "show_inactive": request.GET.get("show_inactive") == "1",
            },
        },
    )


@login_required
@permission_required("hr.view_employee", raise_exception=True)
def employee_detail(request, pk):
    employee = get_object_or_404(
        _employee_queryset(request).prefetch_related(
            "contracts",
            "campaign_records__campaign",
            "change_logs",
        ),
        pk=pk,
    )
    audit_logs = AuditLog.objects.filter(
        model_name="Employee",
        object_id=str(employee.pk),
    ).select_related("actor")[:20]
    return render(
        request,
        "hr/employees/detail.html",
        {
            "employee": employee,
            "contracts": employee.contracts.all(),
            "probation": getattr(employee, "probation", None),
            "campaign_records": employee.campaign_records.select_related("campaign").all(),
            "changes": employee.change_logs.all()[:12],
            "audit_entries": audit_logs_with_diffs(audit_logs),
        },
    )


@login_required
@permission_required("hr.add_employee", raise_exception=True)
def employee_create(request):
    if request.method == "POST":
        form = EmployeeForm(request.POST, user=request.user)
        if form.is_valid():
            employee = form.save()
            write_audit_log(
                request,
                AuditLog.ACTION_CREATE,
                "Создана карточка сотрудника",
                obj=employee,
                after=snapshot_instance(employee),
                employee=employee,
            )
            messages.success(request, "Сотрудник создан.")
            return redirect("employee_detail", pk=employee.pk)
    else:
        form = EmployeeForm(user=request.user)

    return render(
        request,
        "hr/employees/form.html",
        {"form": form, "title": "Создание сотрудника"},
    )


@login_required
@permission_required("hr.change_employee", raise_exception=True)
def employee_edit(request, pk):
    employee = get_object_or_404(_employee_queryset(request), pk=pk)
    before = snapshot_instance(employee)
    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=employee, user=request.user)
        if form.is_valid():
            employee = form.save()
            write_audit_log(
                request,
                AuditLog.ACTION_UPDATE,
                "Обновлена карточка сотрудника",
                obj=employee,
                before=before,
                after=snapshot_instance(employee),
                employee=employee,
            )
            messages.success(request, "Изменения сохранены.")
            return redirect("employee_detail", pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee, user=request.user)

    return render(
        request,
        "hr/employees/form.html",
        {"form": form, "title": "Редактирование сотрудника", "employee": employee},
    )


@login_required
@permission_required("hr.change_employee", raise_exception=True)
@require_POST
def employee_terminate(request, pk):
    employee = get_object_or_404(_employee_queryset(request), pk=pk)
    before = snapshot_instance(employee)
    employee.is_active = False
    employee.dismissal_date = timezone.localdate()
    employee.save(update_fields=["is_active", "dismissal_date"])
    write_audit_log(
        request,
        AuditLog.ACTION_UPDATE,
        "Сотрудник уволен",
        obj=employee,
        before=before,
        after=snapshot_instance(employee),
        employee=employee,
    )
    messages.warning(request, "Сотрудник переведён в статус уволенного.")
    return redirect(request.POST.get("next") or reverse("employee_detail", args=[employee.pk]))


@login_required
@permission_required("hr.change_employee", raise_exception=True)
@require_POST
def employee_restore(request, pk):
    employee = get_object_or_404(_employee_queryset(request), pk=pk)
    before = snapshot_instance(employee)
    employee.is_active = True
    employee.dismissal_date = None
    employee.save(update_fields=["is_active", "dismissal_date"])
    write_audit_log(
        request,
        AuditLog.ACTION_UPDATE,
        "Сотрудник возвращён в штат",
        obj=employee,
        before=before,
        after=snapshot_instance(employee),
        employee=employee,
    )
    messages.success(request, "Сотрудник возвращён в штат.")
    return redirect(request.POST.get("next") or reverse("employee_detail", args=[employee.pk]))


@login_required
@permission_required("hr.view_employee", raise_exception=True)
def employees_export(request):
    employees = _filtered_employees(request)
    rows_count = employees.count()
    content = build_employee_workbook(employees)
    write_audit_log(
        request,
        AuditLog.ACTION_EXPORT,
        f"Экспорт сотрудников в Excel: {rows_count} строк",
        after={"rows": rows_count, "filters": dict(request.GET.lists())},
        write_change=False,
    )
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="employees.xlsx"'
    return response


@login_required
@permission_required(("hr.add_employee", "hr.change_employee"), raise_exception=True)
def employees_import(request):
    if not user_has_global_employee_scope(request.user):
        raise PermissionDenied
    result = None
    preview = request.session.get("employee_import_preview")
    if request.method == "POST":
        action = request.POST.get("action", "preview")
        if action == "confirm":
            rows = request.session.get("employee_import_rows", [])
            result = apply_employee_import_rows(rows)
            request.session.pop("employee_import_rows", None)
            request.session.pop("employee_import_preview", None)
            preview = None
            if result["errors"]:
                messages.warning(request, "Импорт применён с ошибками.")
            else:
                messages.success(request, "Импорт сотрудников применён.")
            write_audit_log(
                request,
                AuditLog.ACTION_IMPORT,
                (
                    "Импорт сотрудников подтверждён: "
                    f"{result['created']} создано, {result['updated']} обновлено, "
                    f"{len(result['errors'])} ошибок"
                ),
                after=result,
                write_change=False,
            )
        else:
            upload = request.FILES.get("file")
            if not upload:
                messages.error(request, "Выберите файл .xlsx для предпросмотра.")
            elif not upload.name.lower().endswith(".xlsx"):
                messages.error(request, "Поддерживается только формат .xlsx.")
            elif upload.size > 5 * 1024 * 1024:
                messages.error(request, "Файл слишком большой. Максимальный размер — 5 МБ.")
            else:
                try:
                    preview = preview_employees_from_xlsx(upload)
                except Exception as exc:
                    preview = {
                        "created": 0,
                        "updated": 0,
                        "skipped": 0,
                        "errors": [f"Файл не удалось прочитать: {exc}"],
                        "operations": [],
                        "rows": [],
                    }
                request.session["employee_import_preview"] = preview
                request.session["employee_import_rows"] = preview.get("rows", [])
                if preview["errors"]:
                    messages.warning(request, "Предпросмотр построен с ошибками.")
                else:
                    messages.success(request, "Предпросмотр готов. Проверьте изменения и подтвердите импорт.")

    return render(
        request,
        "hr/employees/import.html",
        {"result": result, "preview": preview},
    )


@login_required
@permission_required("hr.view_employee", raise_exception=True)
def employees_import_template(request):
    content = build_employee_workbook(Employee.objects.none(), include_rows=False)
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="employees_import_template.xlsx"'
    return response


@login_required
@permission_required("hr.view_employee", raise_exception=True)
@require_POST
def employee_columns_update(request):
    save_employee_column_preference(
        request.user,
        request.POST.getlist("columns"),
        request.POST.get("page_size"),
    )
    messages.success(request, "Настройки таблицы сохранены.")
    return redirect(request.POST.get("next") or reverse("employees_list"))


def _probation_stage_due(probation, offset_days):
    if offset_days is None:
        return probation.end_date
    return probation.start_date + timedelta(days=offset_days)


def _probation_stage_status(done, due_date, today):
    if done:
        return "done"
    if due_date < today:
        return "overdue"
    if due_date == today:
        return "today"
    return "pending"


@login_required
@permission_required("hr.view_probation", raise_exception=True)
def probation_list(request):
    today = timezone.localdate()
    visible_employee_ids = _employee_queryset(request).values("id")
    probations = Probation.objects.select_related(
        "employee",
        "employee__department",
        "employee__position",
    ).filter(employee_id__in=visible_employee_ids).order_by("end_date")

    rows = []
    for probation in probations:
        stages = []
        for field, (title, offset_days) in PROBATION_STAGE_FIELDS.items():
            due_date = _probation_stage_due(probation, offset_days)
            done = getattr(probation, field)
            stages.append(
                {
                    "field": field,
                    "title": title,
                    "done": done,
                    "due_date": due_date,
                    "status": _probation_stage_status(done, due_date, today),
                }
            )
        rows.append(
            {
                "probation": probation,
                "days_left": (probation.end_date - today).days,
                "stages": stages,
            }
        )

    pending_dismissals = probations.filter(
        result=Probation.RESULT_FAILED,
        employee__is_active=True,
    )

    return render(
        request,
        "hr/probation/list.html",
        {
            "rows": rows,
            "pending_dismissals": pending_dismissals,
        },
    )


@login_required
@permission_required("hr.change_probation", raise_exception=True)
@require_POST
def probation_toggle_stage(request, pk, field):
    if field not in PROBATION_STAGE_FIELDS:
        messages.error(request, "Неизвестный этап испытательного срока.")
        return redirect("probation_list")

    probation = get_object_or_404(Probation.objects.select_related("employee"), pk=pk)
    if not user_can_access_employee(request.user, probation.employee):
        raise PermissionDenied
    before = snapshot_instance(probation)
    setattr(probation, field, not getattr(probation, field))
    probation.save(update_fields=[field])
    write_audit_log(
        request,
        AuditLog.ACTION_UPDATE,
        f"Изменён этап испытательного срока: {field}",
        obj=probation,
        before=before,
        after=snapshot_instance(probation),
        employee=probation.employee,
    )
    return redirect("probation_list")


@login_required
@permission_required("hr.change_probation", raise_exception=True)
@require_POST
def probation_set_result(request, pk):
    probation = get_object_or_404(Probation.objects.select_related("employee"), pk=pk)
    if not user_can_access_employee(request.user, probation.employee):
        raise PermissionDenied
    before = snapshot_instance(probation)
    result = request.POST.get("result")
    if result not in [Probation.RESULT_PASSED, Probation.RESULT_FAILED]:
        messages.error(request, "Некорректный результат испытательного срока.")
        return redirect("probation_list")

    probation.result = result
    probation.save(update_fields=["result"])
    write_audit_log(
        request,
        AuditLog.ACTION_UPDATE,
        f"Испытательный срок: {probation.get_result_display()}",
        obj=probation,
        before=before,
        after=snapshot_instance(probation),
        employee=probation.employee,
    )
    messages.success(request, "Результат испытательного срока обновлён.")
    return redirect("probation_list")


def _build_department_tree():
    departments = list(
        Department.objects.annotate(
            direct_count=Count("employees", filter=Q(employees__is_active=True))
        ).order_by("name")
    )
    children = defaultdict(list)
    by_id = {department.id: department for department in departments}
    direct_counts = {department.id: department.direct_count for department in departments}

    for department in departments:
        children[department.parent_id].append(department)

    def build_node(department):
        child_nodes = [build_node(child) for child in children[department.id]]
        total_count = direct_counts[department.id] + sum(
            child["total_count"] for child in child_nodes
        )
        return {
            "department": department,
            "children": child_nodes,
            "direct_count": direct_counts[department.id],
            "total_count": total_count,
        }

    root_departments = [department for department in departments if department.parent_id not in by_id]
    return [build_node(department) for department in root_departments]


@login_required
@permission_required("hr.view_department", raise_exception=True)
def departments_list(request):
    return render(request, "hr/departments/list.html", {"tree": _build_department_tree()})


@login_required
@permission_required("hr.view_department", raise_exception=True)
def departments_export(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="departments.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["id", "name", "parent", "active_employees"])
    departments = Department.objects.annotate(
        active_employees=Count("employees", filter=Q(employees__is_active=True))
    ).select_related("parent")
    for department in departments:
        writer.writerow(
            [
                department.id,
                department.name,
                department.parent.name if department.parent else "",
                department.active_employees,
            ]
        )
    write_audit_log(
        request,
        AuditLog.ACTION_EXPORT,
        "Выгрузка структуры подразделений",
        after={"rows": departments.count()},
        write_change=False,
    )
    return response


@login_required
@permission_required("hr.add_department", raise_exception=True)
def department_create(request):
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            write_audit_log(
                request,
                AuditLog.ACTION_CREATE,
                "Создано подразделение",
                obj=department,
                after=snapshot_instance(department),
                write_change=False,
            )
            messages.success(request, "Подразделение создано.")
            return redirect("departments_list")
    else:
        form = DepartmentForm()

    return render(
        request,
        "hr/departments/form.html",
        {"form": form, "title": "Создание подразделения"},
    )


@login_required
@permission_required("hr.change_department", raise_exception=True)
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    before = snapshot_instance(department)
    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            department = form.save()
            write_audit_log(
                request,
                AuditLog.ACTION_UPDATE,
                "Обновлено подразделение",
                obj=department,
                before=before,
                after=snapshot_instance(department),
                write_change=False,
            )
            messages.success(request, "Подразделение обновлено.")
            return redirect("departments_list")
    else:
        form = DepartmentForm(instance=department)

    return render(
        request,
        "hr/departments/form.html",
        {"form": form, "title": "Редактирование подразделения"},
    )


def _safe_month_from_request(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if month < 1 or month > 12:
            raise ValueError
        return year, month
    except ValueError:
        return today.year, today.month


def _month_bounds(year, month):
    month_start = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return month_start, next_month - timedelta(days=1)


def _add_calendar_event(events, event_date, event_type, title, url=""):
    if event_date:
        events[event_date].append(
            {
                "type": event_type,
                "title": title,
                "url": url,
            }
        )


@login_required
@permission_required("hr.view_employee", raise_exception=True)
def calendar_view(request):
    year, month = _safe_month_from_request(request)
    selected_types = request.GET.getlist("type") or list(CALENDAR_EVENT_TYPES.keys())
    selected_types = [
        event_type
        for event_type in selected_types
        if event_type in CALENDAR_EVENT_TYPES
    ]
    month_start, month_end = _month_bounds(year, month)
    events = defaultdict(list)
    visible_employees = _employee_queryset(request)

    if "hire" in selected_types:
        employees = visible_employees.filter(
            hire_date__gte=month_start,
            hire_date__lte=month_end,
        )
        for employee in employees:
            _add_calendar_event(
                events,
                employee.hire_date,
                "hire",
                f"Приём: {employee.full_name}",
                reverse("employee_detail", args=[employee.pk]),
            )

    if "dismissal" in selected_types:
        employees = visible_employees.filter(
            dismissal_date__gte=month_start,
            dismissal_date__lte=month_end,
        )
        for employee in employees:
            _add_calendar_event(
                events,
                employee.dismissal_date,
                "dismissal",
                f"Увольнение: {employee.full_name}",
                reverse("employee_detail", args=[employee.pk]),
            )

    if "probation" in selected_types:
        probations = Probation.objects.select_related("employee").filter(
            employee_id__in=visible_employees.values("id"),
            end_date__gte=month_start,
            end_date__lte=month_end,
        )
        for probation in probations:
            _add_calendar_event(
                events,
                probation.end_date,
                "probation",
                f"Конец ИС: {probation.employee.full_name}",
                reverse("probation_list"),
            )

    if "ipr" in selected_types:
        employees = visible_employees.filter(
            ipr_status__in=[Employee.IPR_EXPIRED, Employee.IPR_EXPIRING],
            contract_end_date__gte=month_start,
            contract_end_date__lte=month_end,
        )
        for employee in employees:
            _add_calendar_event(
                events,
                employee.contract_end_date,
                "ipr",
                f"ИПР: {employee.full_name}",
                reverse("employee_detail", args=[employee.pk]),
            )

    if "campaign" in selected_types:
        campaigns = Campaign.objects.filter(
            Q(start_date__gte=month_start, start_date__lte=month_end)
            | Q(default_apply_date__gte=month_start, default_apply_date__lte=month_end)
            | Q(closed_at__gte=month_start, closed_at__lte=month_end)
        )
        for campaign in campaigns:
            _add_calendar_event(
                events,
                campaign.start_date,
                "campaign",
                f"Старт кампании: {campaign}",
                reverse("campaign_detail", args=[campaign.pk]),
            )
            _add_calendar_event(
                events,
                campaign.default_apply_date,
                "campaign",
                f"Применение: {campaign}",
                reverse("campaign_detail", args=[campaign.pk]),
            )
            _add_calendar_event(
                events,
                campaign.closed_at,
                "campaign",
                f"Закрытие: {campaign}",
                reverse("campaign_detail", args=[campaign.pk]),
            )

    import calendar as py_calendar

    month_calendar = py_calendar.Calendar(firstweekday=0)
    weeks = []
    today = timezone.localdate()
    for week in month_calendar.monthdatescalendar(year, month):
        weeks.append(
            [
                {
                    "date": day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "events": events.get(day, []),
                }
                for day in week
            ]
        )

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    def nav_url(nav_year, nav_month):
        params = [("year", nav_year), ("month", nav_month)]
        params.extend(("type", event_type) for event_type in selected_types)
        return "?" + urlencode(params)

    return render(
        request,
        "hr/calendar/month.html",
        {
            "weeks": weeks,
            "month_name": MONTHS_RU[month],
            "year": year,
            "event_types": CALENDAR_EVENT_TYPES,
            "selected_types": selected_types,
            "prev_url": nav_url(prev_year, prev_month),
            "next_url": nav_url(next_year, next_month),
        },
    )


@login_required
@permission_required("hr.view_campaign", raise_exception=True)
def campaigns_list(request):
    campaigns = Campaign.objects.annotate(record_count=Count("records")).order_by(
        "-year",
        "season",
    )
    return render(request, "hr/campaigns/list.html", {"campaigns": campaigns})


@login_required
@permission_required("hr.add_campaign", raise_exception=True)
def campaign_create(request):
    if request.method == "POST":
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save()
            write_audit_log(
                request,
                AuditLog.ACTION_CREATE,
                "Создана кампания",
                obj=campaign,
                after=snapshot_instance(campaign),
                write_change=False,
            )
            messages.success(request, "Кампания создана.")
            return redirect("campaign_detail", pk=campaign.pk)
    else:
        form = CampaignForm()

    return render(
        request,
        "hr/campaigns/form.html",
        {"form": form, "title": "Создание кампании"},
    )


@login_required
@permission_required("hr.view_campaign", raise_exception=True)
def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign.objects.annotate(record_count=Count("records")), pk=pk)
    visible_employee_ids = _employee_queryset(request).values("id")
    records = campaign.records.select_related(
        "employee",
        "employee__department",
        "employee__position",
    ).filter(employee_id__in=visible_employee_ids)
    form = CampaignRecordForm(employee_queryset=_employee_queryset(request).filter(is_active=True))
    return render(
        request,
        "hr/campaigns/detail.html",
        {
            "campaign": campaign,
            "records": records,
            "form": form,
            "departments": Department.objects.order_by("name"),
            "record_status_choices": CampaignRecord.STATUS_CHOICES,
        },
    )


@login_required
@permission_required("hr.add_campaignrecord", raise_exception=True)
@require_POST
def campaign_record_add(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if campaign.status == Campaign.STATUS_CLOSED:
        messages.error(request, "Закрытую кампанию сначала нужно переоткрыть.")
        return redirect("campaign_detail", pk=campaign.pk)
    form = CampaignRecordForm(
        request.POST,
        employee_queryset=_employee_queryset(request).filter(is_active=True),
    )
    if form.is_valid():
        record = form.save(commit=False)
        if not user_can_access_employee(request.user, record.employee):
            raise PermissionDenied
        if campaign.records.filter(employee=record.employee).exists():
            messages.error(request, "Сотрудник уже добавлен в эту кампанию.")
            return redirect("campaign_detail", pk=campaign.pk)
        record.campaign = campaign
        record.save()
        write_audit_log(
            request,
            AuditLog.ACTION_CREATE,
            f"Добавлена запись кампании {campaign}",
            obj=record,
            after=snapshot_instance(record),
            employee=record.employee,
        )
        messages.success(request, "Запись кампании добавлена.")
    else:
        messages.error(request, "Запись не сохранена. Проверьте поля формы.")
    return redirect("campaign_detail", pk=campaign.pk)


@login_required
@permission_required("hr.add_campaignrecord", raise_exception=True)
@require_POST
def campaign_records_bulk_add(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if campaign.status == Campaign.STATUS_CLOSED:
        messages.error(request, "Закрытую кампанию сначала нужно переоткрыть.")
        return redirect("campaign_detail", pk=campaign.pk)
    employees = _employee_queryset(request).filter(is_active=True)
    department_id = request.POST.get("department")
    if department_id:
        employees = employees.filter(department_id=department_id)

    existing_ids = set(campaign.records.values_list("employee_id", flat=True))
    created = 0
    for employee in employees.exclude(id__in=existing_ids):
        CampaignRecord.objects.create(
            campaign=campaign,
            employee=employee,
            status=CampaignRecord.STATUS_MANAGER_REVIEW,
        )
        created += 1

    write_audit_log(
        request,
        AuditLog.ACTION_CREATE,
        f"Массово добавлены записи кампании {campaign}: {created}",
        obj=campaign,
        after={"created_records": created, "department_id": department_id or ""},
        write_change=False,
    )
    messages.success(request, f"Добавлено записей: {created}.")
    return redirect("campaign_detail", pk=campaign.pk)


@login_required
@permission_required("hr.change_campaignrecord", raise_exception=True)
@require_POST
def campaign_record_status_update(request, pk, record_pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if campaign.status == Campaign.STATUS_CLOSED:
        messages.error(request, "Статусы закрытой кампании изменять нельзя.")
        return redirect("campaign_detail", pk=campaign.pk)
    record = get_object_or_404(campaign.records.select_related("employee"), pk=record_pk)
    if not user_can_access_employee(request.user, record.employee):
        raise PermissionDenied
    status = request.POST.get("status")
    if status not in dict(CampaignRecord.STATUS_CHOICES):
        messages.error(request, "Некорректный статус записи кампании.")
        return redirect("campaign_detail", pk=campaign.pk)

    before = snapshot_instance(record)
    record.status = status
    record.save(update_fields=["status"])
    write_audit_log(
        request,
        AuditLog.ACTION_UPDATE,
        f"Статус записи кампании изменён: {record.get_status_display()}",
        obj=record,
        before=before,
        after=snapshot_instance(record),
        employee=record.employee,
    )
    messages.success(request, "Статус записи кампании обновлён.")
    return redirect("campaign_detail", pk=campaign.pk)


@login_required
@permission_required("hr.change_campaign", raise_exception=True)
@require_POST
def campaign_status_update(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    before = snapshot_instance(campaign)
    action = request.POST.get("action")
    if action == "close":
        campaign.status = Campaign.STATUS_CLOSED
        campaign.closed_at = timezone.localdate()
        event = "Кампания закрыта"
    elif action == "reopen":
        campaign.status = Campaign.STATUS_OPEN
        campaign.closed_at = None
        event = "Кампания переоткрыта"
    else:
        messages.error(request, "Неизвестное действие кампании.")
        return redirect("campaign_detail", pk=campaign.pk)
    campaign.save(update_fields=["status", "closed_at"])
    write_audit_log(
        request,
        AuditLog.ACTION_UPDATE,
        event,
        obj=campaign,
        before=before,
        after=snapshot_instance(campaign),
        write_change=False,
    )
    messages.success(request, event)
    return redirect("campaign_detail", pk=campaign.pk)


@login_required
@permission_required("hr.view_position", raise_exception=True)
def positions_directory(request):
    positions = Position.objects.annotate(employee_count=Count("employees")).order_by("name")
    return render(
        request,
        "hr/directories/positions.html",
        {"positions": positions},
    )


@login_required
@permission_required("hr.add_position", raise_exception=True)
def position_create(request):
    if request.method == "POST":
        form = PositionForm(request.POST)
        if form.is_valid():
            position = form.save()
            write_audit_log(
                request,
                AuditLog.ACTION_CREATE,
                "Создана должность",
                obj=position,
                after=snapshot_instance(position),
                write_change=False,
            )
            messages.success(request, "Должность создана.")
            return redirect("positions")
    else:
        form = PositionForm()
    return render(request, "hr/directories/form.html", {"form": form, "title": "Создание должности", "back_url": reverse("positions")})


@login_required
@permission_required("hr.change_position", raise_exception=True)
def position_edit(request, pk):
    position = get_object_or_404(Position, pk=pk)
    before = snapshot_instance(position)
    if request.method == "POST":
        form = PositionForm(request.POST, instance=position)
        if form.is_valid():
            position = form.save()
            write_audit_log(
                request,
                AuditLog.ACTION_UPDATE,
                "Обновлена должность",
                obj=position,
                before=before,
                after=snapshot_instance(position),
                write_change=False,
            )
            messages.success(request, "Должность обновлена.")
            return redirect("positions")
    else:
        form = PositionForm(instance=position)
    return render(request, "hr/directories/form.html", {"form": form, "title": "Редактирование должности", "back_url": reverse("positions")})


@login_required
@permission_required("hr.delete_position", raise_exception=True)
@require_POST
def position_delete(request, pk):
    position = get_object_or_404(Position, pk=pk)
    before = snapshot_instance(position)
    name = position.name
    position.delete()
    write_audit_log(request, AuditLog.ACTION_DELETE, f"Удалена должность: {name}", before=before, write_change=False)
    messages.warning(request, "Должность удалена.")
    return redirect("positions")


@login_required
def reference_directory(request, slug):
    config = _reference_config_or_404(slug)
    if not request.user.has_perm("hr.view_referenceitem"):
        raise PermissionDenied
    items = ReferenceItem.objects.filter(category=config["category"]).order_by("name")
    return render(
        request,
        "hr/directories/reference_items.html",
        {"items": items, "slug": slug, **config},
    )


@login_required
@permission_required("hr.add_referenceitem", raise_exception=True)
def reference_item_create(request, slug):
    config = _reference_config_or_404(slug)
    if request.method == "POST":
        form = ReferenceItemForm(request.POST, category=config["category"])
        if form.is_valid():
            item = form.save()
            write_audit_log(request, AuditLog.ACTION_CREATE, "Создан элемент справочника", obj=item, after=snapshot_instance(item), write_change=False)
            messages.success(request, "Элемент справочника создан.")
            return redirect("reference_directory", slug=slug)
    else:
        form = ReferenceItemForm(category=config["category"])
    return render(request, "hr/directories/form.html", {"form": form, "title": f"Создание: {config['title']}", "back_url": reverse("reference_directory", args=[slug])})


@login_required
@permission_required("hr.change_referenceitem", raise_exception=True)
def reference_item_edit(request, slug, pk):
    config = _reference_config_or_404(slug)
    item = get_object_or_404(ReferenceItem, pk=pk, category=config["category"])
    before = snapshot_instance(item)
    if request.method == "POST":
        form = ReferenceItemForm(request.POST, instance=item, category=config["category"])
        if form.is_valid():
            item = form.save()
            write_audit_log(request, AuditLog.ACTION_UPDATE, "Обновлён элемент справочника", obj=item, before=before, after=snapshot_instance(item), write_change=False)
            messages.success(request, "Элемент справочника обновлён.")
            return redirect("reference_directory", slug=slug)
    else:
        form = ReferenceItemForm(instance=item, category=config["category"])
    return render(request, "hr/directories/form.html", {"form": form, "title": f"Редактирование: {config['title']}", "back_url": reverse("reference_directory", args=[slug])})


@login_required
@permission_required("hr.delete_referenceitem", raise_exception=True)
@require_POST
def reference_item_delete(request, slug, pk):
    config = _reference_config_or_404(slug)
    item = get_object_or_404(ReferenceItem, pk=pk, category=config["category"])
    before = snapshot_instance(item)
    name = item.name
    item.delete()
    write_audit_log(request, AuditLog.ACTION_DELETE, f"Удалён элемент справочника: {name}", before=before, write_change=False)
    messages.warning(request, "Элемент справочника удалён.")
    return redirect("reference_directory", slug=slug)


@login_required
@permission_required("hr.view_emailtemplate", raise_exception=True)
def email_templates_directory(request):
    templates = EmailTemplate.objects.order_by("name")
    return render(request, "hr/directories/email_templates.html", {"templates": templates})


@login_required
@permission_required("hr.add_emailtemplate", raise_exception=True)
def email_template_create(request):
    if request.method == "POST":
        form = EmailTemplateForm(request.POST)
        if form.is_valid():
            template = form.save()
            write_audit_log(request, AuditLog.ACTION_CREATE, "Создан шаблон письма", obj=template, after=snapshot_instance(template), write_change=False)
            messages.success(request, "Шаблон письма создан.")
            return redirect("mail_templates")
    else:
        form = EmailTemplateForm()
    return render(request, "hr/directories/form.html", {"form": form, "title": "Создание шаблона письма", "back_url": reverse("mail_templates")})


@login_required
@permission_required("hr.change_emailtemplate", raise_exception=True)
def email_template_edit(request, pk):
    template = get_object_or_404(EmailTemplate, pk=pk)
    before = snapshot_instance(template)
    if request.method == "POST":
        form = EmailTemplateForm(request.POST, instance=template)
        if form.is_valid():
            template = form.save()
            write_audit_log(request, AuditLog.ACTION_UPDATE, "Обновлён шаблон письма", obj=template, before=before, after=snapshot_instance(template), write_change=False)
            messages.success(request, "Шаблон письма обновлён.")
            return redirect("mail_templates")
    else:
        form = EmailTemplateForm(instance=template)
    return render(request, "hr/directories/form.html", {"form": form, "title": "Редактирование шаблона письма", "back_url": reverse("mail_templates")})


@login_required
@permission_required("hr.delete_emailtemplate", raise_exception=True)
@require_POST
def email_template_delete(request, pk):
    template = get_object_or_404(EmailTemplate, pk=pk)
    before = snapshot_instance(template)
    name = template.name
    template.delete()
    write_audit_log(request, AuditLog.ACTION_DELETE, f"Удалён шаблон письма: {name}", before=before, write_change=False)
    messages.warning(request, "Шаблон письма удалён.")
    return redirect("mail_templates")


def _reference_config_or_404(slug):
    config = REFERENCE_DIRECTORY_CONFIG.get(slug)
    if not config:
        raise PermissionDenied
    return config


@login_required
def simple_page(request, page):
    required_permissions = {
        "guide": "hr.view_employee",
        "positions": "hr.view_position",
        "mail_templates": "hr.view_employee",
        "users": "auth.view_user",
        "data_audit": "hr.view_auditlog",
        "action_log": "hr.view_auditlog",
    }
    permission = required_permissions.get(page)
    if permission and not request.user.has_perm(permission):
        raise PermissionDenied

    page_config = SIMPLE_PAGES[page]
    context = {
        "title": page_config["title"],
        "description": page_config["description"],
        "page": page,
    }
    if page == "positions":
        context["positions"] = Position.objects.annotate(employee_count=Count("employees"))
    if page == "users":
        context["users"] = get_user_model().objects.prefetch_related("groups").order_by("username")
    if page == "data_audit":
        audit_logs = AuditLog.objects.select_related("actor").filter(
            action__in=[AuditLog.ACTION_CREATE, AuditLog.ACTION_UPDATE, AuditLog.ACTION_DELETE]
        )
        if not user_has_global_employee_scope(request.user):
            visible_ids = [str(pk) for pk in _employee_queryset(request).values_list("id", flat=True)]
            audit_logs = audit_logs.filter(model_name="Employee", object_id__in=visible_ids)
        context["audit_entries"] = audit_logs_with_diffs(audit_logs[:50])
    if page == "action_log":
        audit_logs = AuditLog.objects.select_related("actor").filter(
            action__in=[
                AuditLog.ACTION_LOGIN,
                AuditLog.ACTION_IMPORT,
                AuditLog.ACTION_EXPORT,
                AuditLog.ACTION_OTHER,
            ]
        )
        if not user_has_global_employee_scope(request.user):
            audit_logs = audit_logs.filter(actor=request.user)
        context["audit_logs"] = audit_logs[:50]
    return render(request, "hr/simple_page.html", context)
