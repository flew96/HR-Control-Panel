from django import forms

from django.core.exceptions import ValidationError

from .access import accessible_department_ids, scoped_employee_queryset, user_has_global_employee_scope
from .models import Campaign, CampaignRecord, Department, EmailTemplate, Employee, Position, ReferenceItem


class DateInput(forms.DateInput):
    input_type = "date"


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "last_name",
            "first_name",
            "middle_name",
            "email",
            "department",
            "position",
            "manager",
            "hire_date",
            "dismissal_date",
            "dismissal_reason",
            "is_active",
            "ipr_status",
            "contract_type",
            "contract_end_date",
            "salary_gross",
            "salary_net",
            "currency",
        ]
        widgets = {
            "hire_date": DateInput(),
            "dismissal_date": DateInput(),
            "contract_end_date": DateInput(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        manager_queryset = Employee.objects.order_by(
            "last_name",
            "first_name",
        )
        if user is not None:
            manager_queryset = scoped_employee_queryset(user, manager_queryset)
            if not user_has_global_employee_scope(user):
                self.fields["department"].queryset = Department.objects.filter(
                    id__in=accessible_department_ids(user)
                ).order_by("name")
        if self.instance.pk:
            manager_queryset = manager_queryset.exclude(pk=self.instance.pk)
        self.fields["manager"].queryset = manager_queryset
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "checkbox-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if not email:
            return ""
        duplicates = Employee.objects.filter(email__iexact=email)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError("Сотрудник с таким email уже существует.")
        return email

    def clean(self):
        cleaned = super().clean()
        manager = cleaned.get("manager")
        if manager and self.instance.pk:
            seen = set()
            current = manager
            while current and current.pk not in seen:
                if current.pk == self.instance.pk:
                    self.add_error("manager", "Нельзя назначить подчинённого руководителем и создать цикл.")
                    break
                seen.add(current.pk)
                current = current.manager

        hire_date = cleaned.get("hire_date")
        dismissal_date = cleaned.get("dismissal_date")
        if hire_date and dismissal_date and dismissal_date < hire_date:
            self.add_error("dismissal_date", "Дата увольнения не может быть раньше даты найма.")
        for field_name in ("salary_gross", "salary_net"):
            value = cleaned.get(field_name)
            if value is not None and value < 0:
                self.add_error(field_name, "Сумма не может быть отрицательной.")
        return cleaned


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "parent"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_parent(self):
        parent = self.cleaned_data.get("parent")
        if not parent or not self.instance.pk:
            return parent
        if parent.pk == self.instance.pk:
            raise ValidationError("Подразделение не может быть родителем самого себя.")
        current = parent
        seen = set()
        while current and current.pk not in seen:
            if current.pk == self.instance.pk:
                raise ValidationError("Нельзя выбрать дочернее подразделение: получится цикл.")
            seen.add(current.pk)
            current = current.parent
        return parent


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = [
            "season",
            "year",
            "status",
            "start_date",
            "default_apply_date",
            "closed_at",
        ]
        widgets = {
            "start_date": DateInput(),
            "default_apply_date": DateInput(),
            "closed_at": DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class CampaignRecordForm(forms.ModelForm):
    class Meta:
        model = CampaignRecord
        fields = ["employee", "status", "value", "comment"]

    def __init__(self, *args, **kwargs):
        employee_queryset = kwargs.pop("employee_queryset", None)
        super().__init__(*args, **kwargs)
        queryset = Employee.objects.select_related(
            "department",
            "position",
        ).order_by("last_name", "first_name")
        if employee_queryset is not None:
            queryset = employee_queryset.select_related("department", "position").order_by(
                "last_name", "first_name"
            )
        self.fields["employee"].queryset = queryset
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ReferenceItemForm(forms.ModelForm):
    class Meta:
        model = ReferenceItem
        fields = ["category", "code", "name", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        category = kwargs.pop("category", None)
        super().__init__(*args, **kwargs)
        if category:
            self.fields["category"].initial = category
            self.fields["category"].widget = forms.HiddenInput()
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "checkbox-input")
            elif not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs.setdefault("class", "form-control")


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ["name", "subject", "body", "is_active"]
        widgets = {"body": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "checkbox-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")
