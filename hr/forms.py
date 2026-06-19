from django import forms

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
