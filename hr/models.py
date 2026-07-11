from django.conf import settings
from django.db import models


def default_employee_columns():
    return [
        "select",
        "full_name",
        "department",
        "position",
        "manager",
        "ipr_status",
        "contract_type",
        "salary_gross",
        "salary_net",
        "currency",
    ]


class Department(models.Model):
    name = models.CharField(max_length=160)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Position(models.Model):
    name = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    IPR_ACTUAL = "actual"
    IPR_NONE = "none"
    IPR_EXPIRED = "expired"
    IPR_EXPIRING = "expiring"

    IPR_STATUS_CHOICES = [
        (IPR_ACTUAL, "актуален"),
        (IPR_NONE, "нет ИПР"),
        (IPR_EXPIRED, "устарел"),
        (IPR_EXPIRING, "истекает"),
    ]

    CONTRACT_LABOR = "labor"
    CONTRACT_GPH = "gph"
    CONTRACT_SELF_EMPLOYED = "self_employed"

    CONTRACT_TYPE_CHOICES = [
        (CONTRACT_LABOR, "трудовой договор"),
        (CONTRACT_GPH, "GPH"),
        (CONTRACT_SELF_EMPLOYED, "самозанятый"),
    ]

    CURRENCY_CHOICES = [
        ("RUB", "RUB"),
        ("EUR", "EUR"),
    ]

    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    middle_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
    )
    hire_date = models.DateField(null=True, blank=True)
    dismissal_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    ipr_status = models.CharField(
        max_length=20,
        choices=IPR_STATUS_CHOICES,
        default=IPR_NONE,
    )
    contract_type = models.CharField(
        max_length=20,
        choices=CONTRACT_TYPE_CHOICES,
        blank=True,
    )
    contract_end_date = models.DateField(null=True, blank=True)
    salary_gross = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    salary_net = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="RUB")
    dismissal_reason = models.ForeignKey(
        "ReferenceItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dismissed_employees",
        limit_choices_to={"category": "dismissal_reason"},
    )

    class Meta:
        ordering = ["last_name", "first_name", "middle_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(part for part in parts if part).strip()


class Probation(models.Model):
    RESULT_PENDING = "pending"
    RESULT_PASSED = "passed"
    RESULT_FAILED = "failed"

    RESULT_CHOICES = [
        (RESULT_PENDING, "ожидает"),
        (RESULT_PASSED, "пройден"),
        (RESULT_FAILED, "не пройден"),
    ]

    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="probation",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    week_1_done = models.BooleanField(default=False)
    month_1_done = models.BooleanField(default=False)
    middle_review_done = models.BooleanField(default=False)
    month_2_done = models.BooleanField(default=False)
    final_review_done = models.BooleanField(default=False)
    final_survey_done = models.BooleanField(default=False)
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default=RESULT_PENDING,
    )
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["end_date", "employee__last_name"]

    def __str__(self):
        return f"{self.employee} - {self.get_result_display()}"


class Campaign(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "открыта"),
        (STATUS_CLOSED, "закрыта"),
    ]

    season = models.CharField(max_length=80)
    year = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    start_date = models.DateField()
    default_apply_date = models.DateField(null=True, blank=True)
    closed_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-year", "season"]

    def __str__(self):
        return f"{self.season} {self.year}"


class CampaignRecord(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_MANAGER_REVIEW = "manager_review"
    STATUS_MANAGER_APPROVED = "manager_approved"
    STATUS_HR_APPROVED = "hr_approved"
    STATUS_APPLIED = "applied"
    STATUS_REJECTED = "rejected"
    STATUS_DONE = "done"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "активна"),
        (STATUS_MANAGER_REVIEW, "у руководителя"),
        (STATUS_MANAGER_APPROVED, "согласована руководителем"),
        (STATUS_HR_APPROVED, "согласована HR"),
        (STATUS_APPLIED, "применена"),
        (STATUS_REJECTED, "отклонена"),
        (STATUS_DONE, "завершена"),
        (STATUS_CANCELLED, "отменена"),
    ]

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="records",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="campaign_records",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["employee__last_name", "employee__first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "employee"],
                name="unique_campaign_employee_record",
            )
        ]

    def __str__(self):
        return f"{self.campaign}: {self.employee}"


class Contract(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    contract_type = models.CharField(max_length=20, choices=Employee.CONTRACT_TYPE_CHOICES)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["end_date"]

    def __str__(self):
        return f"{self.employee} - {self.get_contract_type_display()}"


class ChangeLog(models.Model):
    created_at = models.DateTimeField()
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="change_logs",
    )
    event = models.CharField(max_length=255)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        employee = self.employee.full_name if self.employee else "Система"
        return f"{self.created_at:%Y-%m-%d}: {employee} - {self.event}"


class AuditLog(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_IMPORT = "import"
    ACTION_EXPORT = "export"
    ACTION_LOGIN = "login"
    ACTION_OTHER = "other"

    ACTION_CHOICES = [
        (ACTION_CREATE, "создание"),
        (ACTION_UPDATE, "изменение"),
        (ACTION_DELETE, "удаление"),
        (ACTION_IMPORT, "импорт"),
        (ACTION_EXPORT, "экспорт"),
        (ACTION_LOGIN, "вход"),
        (ACTION_OTHER, "другое"),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=120, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    event = models.CharField(max_length=255)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["action", "model_name"]),
        ]

    def __str__(self):
        actor = self.actor.get_username() if self.actor else "system"
        return f"{self.created_at:%Y-%m-%d %H:%M}: {actor} - {self.event}"


class EmployeeColumnPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_column_preference",
    )
    columns = models.JSONField(default=default_employee_columns)
    page_size = models.PositiveIntegerField(default=25)

    class Meta:
        verbose_name = "employee column preference"
        verbose_name_plural = "employee column preferences"

    def __str__(self):
        return f"{self.user} employee columns"


class ReferenceItem(models.Model):
    CATEGORY_CONTRACT_TYPE = "contract_type"
    CATEGORY_DISMISSAL_REASON = "dismissal_reason"
    CATEGORY_CALENDAR_EVENT_TYPE = "calendar_event_type"

    CATEGORY_CHOICES = [
        (CATEGORY_CONTRACT_TYPE, "Типы договоров"),
        (CATEGORY_DISMISSAL_REASON, "Причины увольнения"),
        (CATEGORY_CALENDAR_EVENT_TYPE, "Типы событий календаря"),
    ]

    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]
        unique_together = [("category", "code")]

    def __str__(self):
        return self.name


class EmailTemplate(models.Model):
    name = models.CharField(max_length=160, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserDepartmentAccess(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="department_accesses",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="user_accesses",
    )
    include_children = models.BooleanField(default=True)

    class Meta:
        unique_together = [("user", "department")]
        verbose_name = "user department access"
        verbose_name_plural = "user department accesses"

    def __str__(self):
        suffix = " + children" if self.include_children else ""
        return f"{self.user} -> {self.department}{suffix}"
