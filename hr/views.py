import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CampaignForm, CampaignRecordForm, DepartmentForm, EmployeeForm
from .models import (
    Campaign,
    CampaignRecord,
    ChangeLog,
    Contract,
    Department,
    Employee,
    Position,
    Probation,
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
        "description": "Короткий раздел для будущей базы знаний HR-процессов.",
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
        "description": "Заготовка под управление пользователями и ролями.",
    },
    "data_audit": {
        "title": "Аудит-лог данных",
        "description": "Раздел для контроля изменений в критичных данных.",
    },
    "action_log": {
        "title": "Журнал действий",
        "description": "Последние события и системные действия.",
    },
}


def _add_change(employee, event):
    ChangeLog.objects.create(
        created_at=timezone.now(),
        employee=employee,
        event=event,
    )


def dashboard(request):
    today = timezone.localdate()
    soon = today + timedelta(days=30)

    expiring_contracts = (
        Contract.objects.select_related("employee")
        .filter(employee__is_active=True, end_date__gte=today, end_date__lte=soon)
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
            "value": Employee.objects.filter(is_active=True).count(),
            "accent": "blue",
        },
        {
            "label": "Устаревшие ИПР",
            "value": Employee.objects.filter(ipr_status=Employee.IPR_EXPIRED).count(),
            "accent": "red",
        },
        {
            "label": "ИПР истекает за 30 дней",
            "value": Employee.objects.filter(ipr_status=Employee.IPR_EXPIRING).count(),
            "accent": "amber",
        },
        {
            "label": "Открытые кампании",
            "value": Campaign.objects.filter(status=Campaign.STATUS_OPEN).count(),
            "accent": "green",
        },
        {
            "label": "Активные записи кампаний",
            "value": CampaignRecord.objects.filter(
                campaign__status=Campaign.STATUS_OPEN,
                status=CampaignRecord.STATUS_ACTIVE,
            ).count(),
            "accent": "violet",
        },
    ]

    recent_changes = ChangeLog.objects.select_related("employee").order_by("-created_at")[:8]

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
    employees = Employee.objects.select_related("department", "position", "manager")

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


def employees_list(request):
    employees = _filtered_employees(request)
    total_count = employees.count()
    missing_salary_count = employees.filter(
        Q(salary_gross__isnull=True) | Q(salary_net__isnull=True)
    ).count()

    payroll_by_currency = list(
        employees.values("currency")
        .annotate(
            employees_count=Count("id"),
            gross_total=Sum("salary_gross"),
            net_total=Sum("salary_net"),
            gross_avg=Avg("salary_gross"),
            net_avg=Avg("salary_net"),
        )
        .order_by("currency")
    )

    return render(
        request,
        "hr/employees/list.html",
        {
            "employees": employees,
            "departments": Department.objects.order_by("name"),
            "positions": Position.objects.order_by("name"),
            "ipr_status_choices": Employee.IPR_STATUS_CHOICES,
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


def employee_detail(request, pk):
    employee = get_object_or_404(
        Employee.objects.select_related("department", "position", "manager").prefetch_related(
            "contracts",
            "campaign_records__campaign",
            "change_logs",
        ),
        pk=pk,
    )
    return render(
        request,
        "hr/employees/detail.html",
        {
            "employee": employee,
            "contracts": employee.contracts.all(),
            "campaign_records": employee.campaign_records.select_related("campaign").all(),
            "changes": employee.change_logs.all()[:12],
        },
    )


def employee_create(request):
    if request.method == "POST":
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save()
            _add_change(employee, "Создана карточка сотрудника")
            messages.success(request, "Сотрудник создан.")
            return redirect("employee_detail", pk=employee.pk)
    else:
        form = EmployeeForm()

    return render(
        request,
        "hr/employees/form.html",
        {"form": form, "title": "Создание сотрудника"},
    )


def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            employee = form.save()
            _add_change(employee, "Обновлена карточка сотрудника")
            messages.success(request, "Изменения сохранены.")
            return redirect("employee_detail", pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)

    return render(
        request,
        "hr/employees/form.html",
        {"form": form, "title": "Редактирование сотрудника", "employee": employee},
    )


@require_POST
def employee_terminate(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    employee.is_active = False
    employee.dismissal_date = timezone.localdate()
    employee.save(update_fields=["is_active", "dismissal_date"])
    _add_change(employee, "Сотрудник уволен")
    messages.warning(request, "Сотрудник переведён в статус уволенного.")
    return redirect(request.POST.get("next") or reverse("employee_detail", args=[employee.pk]))


@require_POST
def employee_restore(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    employee.is_active = True
    employee.dismissal_date = None
    employee.save(update_fields=["is_active", "dismissal_date"])
    _add_change(employee, "Сотрудник возвращён в штат")
    messages.success(request, "Сотрудник возвращён в штат.")
    return redirect(request.POST.get("next") or reverse("employee_detail", args=[employee.pk]))


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


def probation_list(request):
    today = timezone.localdate()
    probations = Probation.objects.select_related(
        "employee",
        "employee__department",
        "employee__position",
    ).order_by("end_date")

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


@require_POST
def probation_toggle_stage(request, pk, field):
    if field not in PROBATION_STAGE_FIELDS:
        messages.error(request, "Неизвестный этап испытательного срока.")
        return redirect("probation_list")

    probation = get_object_or_404(Probation.objects.select_related("employee"), pk=pk)
    setattr(probation, field, not getattr(probation, field))
    probation.save(update_fields=[field])
    _add_change(probation.employee, f"Изменён этап испытательного срока: {field}")
    return redirect("probation_list")


@require_POST
def probation_set_result(request, pk):
    probation = get_object_or_404(Probation.objects.select_related("employee"), pk=pk)
    result = request.POST.get("result")
    if result not in [Probation.RESULT_PASSED, Probation.RESULT_FAILED]:
        messages.error(request, "Некорректный результат испытательного срока.")
        return redirect("probation_list")

    probation.result = result
    probation.save(update_fields=["result"])
    _add_change(probation.employee, f"Испытательный срок: {probation.get_result_display()}")
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


def departments_list(request):
    return render(
        request,
        "hr/departments/list.html",
        {"tree": _build_department_tree()},
    )


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
    return response


def department_create(request):
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Подразделение создано.")
            return redirect("departments_list")
    else:
        form = DepartmentForm()

    return render(
        request,
        "hr/departments/form.html",
        {"form": form, "title": "Создание подразделения"},
    )


def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
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


def calendar_view(request):
    year, month = _safe_month_from_request(request)
    selected_types = request.GET.getlist("type") or list(CALENDAR_EVENT_TYPES.keys())
    selected_types = [event_type for event_type in selected_types if event_type in CALENDAR_EVENT_TYPES]
    month_start, month_end = _month_bounds(year, month)
    events = defaultdict(list)

    if "hire" in selected_types:
        employees = Employee.objects.filter(
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
        employees = Employee.objects.filter(
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
        employees = Employee.objects.filter(
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


def campaigns_list(request):
    campaigns = Campaign.objects.annotate(record_count=Count("records")).order_by(
        "-year",
        "season",
    )
    return render(
        request,
        "hr/campaigns/list.html",
        {"campaigns": campaigns},
    )


def campaign_create(request):
    if request.method == "POST":
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save()
            messages.success(request, "Кампания создана.")
            return redirect("campaign_detail", pk=campaign.pk)
    else:
        form = CampaignForm()

    return render(
        request,
        "hr/campaigns/form.html",
        {"form": form, "title": "Создание кампании"},
    )


def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign.objects.annotate(record_count=Count("records")), pk=pk)
    records = campaign.records.select_related("employee", "employee__department", "employee__position")
    form = CampaignRecordForm()
    return render(
        request,
        "hr/campaigns/detail.html",
        {
            "campaign": campaign,
            "records": records,
            "form": form,
        },
    )


@require_POST
def campaign_record_add(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    form = CampaignRecordForm(request.POST)
    if form.is_valid():
        record = form.save(commit=False)
        record.campaign = campaign
        record.save()
        _add_change(record.employee, f"Добавлена запись кампании {campaign}")
        messages.success(request, "Запись кампании добавлена.")
    else:
        messages.error(request, "Запись не сохранена. Проверьте поля формы.")
    return redirect("campaign_detail", pk=campaign.pk)


def simple_page(request, page):
    page_config = SIMPLE_PAGES[page]
    context = {
        "title": page_config["title"],
        "description": page_config["description"],
        "page": page,
    }
    if page == "positions":
        context["positions"] = Position.objects.annotate(employee_count=Count("employees"))
    if page in ["data_audit", "action_log"]:
        context["changes"] = ChangeLog.objects.select_related("employee")[:30]
    return render(request, "hr/simple_page.html", context)
