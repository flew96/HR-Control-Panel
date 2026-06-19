from django.db import models


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
    STATUS_DONE = "done"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "активна"),
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

