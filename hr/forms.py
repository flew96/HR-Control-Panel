from django import forms

from .models import Campaign, CampaignRecord, Department, Employee


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
        super().__init__(*args, **kwargs)
        self.fields["manager"].queryset = Employee.objects.order_by(
            "last_name",
            "first_name",
        )
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "checkbox-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "parent"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


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
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.select_related(
            "department",
            "position",
        ).order_by("last_name", "first_name")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
