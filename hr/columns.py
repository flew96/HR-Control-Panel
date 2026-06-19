from .models import EmployeeColumnPreference, default_employee_columns


EMPLOYEE_COLUMNS = [
    ("select", ""),
    ("full_name", "ФИО"),
    ("department", "Подразделение"),
    ("position", "Должность"),
    ("manager", "Руководитель"),
    ("email", "Email"),
    ("ipr_status", "Статус ИПР"),
    ("contract_type", "Тип договора"),
    ("hire_date", "Дата найма"),
    ("contract_end_date", "Конец договора"),
    ("salary_gross", "Gross"),
    ("salary_net", "Net"),
    ("currency", "Валюта"),
    ("is_active", "Статус"),
]

EMPLOYEE_COLUMN_KEYS = [key for key, _label in EMPLOYEE_COLUMNS]
DEFAULT_PAGE_SIZE = 25
PAGE_SIZE_CHOICES = [10, 25, 50, 100]


def get_employee_column_preference(user):
    if not user.is_authenticated:
        return default_employee_columns(), DEFAULT_PAGE_SIZE

    preference, _created = EmployeeColumnPreference.objects.get_or_create(user=user)
    columns = [
        column
        for column in preference.columns
        if column in EMPLOYEE_COLUMN_KEYS
    ]
    if not columns:
        columns = default_employee_columns()
    page_size = preference.page_size if preference.page_size in PAGE_SIZE_CHOICES else DEFAULT_PAGE_SIZE
    return columns, page_size


def save_employee_column_preference(user, columns, page_size):
    allowed_columns = [
        column
        for column in columns
        if column in EMPLOYEE_COLUMN_KEYS
    ]
    if "full_name" not in allowed_columns:
        allowed_columns.insert(0, "full_name")
    if not allowed_columns:
        allowed_columns = default_employee_columns()

    try:
        clean_page_size = int(page_size)
    except (TypeError, ValueError):
        clean_page_size = DEFAULT_PAGE_SIZE
    if clean_page_size not in PAGE_SIZE_CHOICES:
        clean_page_size = DEFAULT_PAGE_SIZE

    preference, _created = EmployeeColumnPreference.objects.get_or_create(user=user)
    preference.columns = allowed_columns
    preference.page_size = clean_page_size
    preference.save(update_fields=["columns", "page_size"])
    return preference

