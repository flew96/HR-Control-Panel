from django.db.models import Q

from .models import Department, Employee


GLOBAL_EMPLOYEE_SCOPE_GROUPS = ["HR Admin", "HR Manager", "HR Viewer"]


def user_has_global_employee_scope(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.groups.filter(name__in=GLOBAL_EMPLOYEE_SCOPE_GROUPS).exists():
        return True
    if user.groups.filter(name__in=["HRBP", "Line Manager"]).exists():
        return False
    return user.has_perm("hr.view_employee")


def scoped_employee_queryset(user, queryset=None):
    queryset = queryset or Employee.objects.all()
    if not user.is_authenticated:
        return queryset.none()
    if user_has_global_employee_scope(user):
        return queryset

    department_ids = _accessible_department_ids(user)
    manager_employee = Employee.objects.filter(email__iexact=user.email).first() if user.email else None
    is_restricted_role = user.groups.filter(name__in=["HRBP", "Line Manager"]).exists()

    if not is_restricted_role and not department_ids and not manager_employee and user.has_perm("hr.view_employee"):
        return queryset

    filters = Q()
    if department_ids:
        filters |= Q(department_id__in=department_ids)
    if manager_employee:
        filters |= Q(manager=manager_employee) | Q(pk=manager_employee.pk)

    if not filters:
        return queryset.none()
    return queryset.filter(filters).distinct()


def user_can_access_employee(user, employee):
    return scoped_employee_queryset(user, Employee.objects.filter(pk=employee.pk)).exists()


def accessible_department_ids(user):
    if user_has_global_employee_scope(user):
        return set(Department.objects.values_list("id", flat=True))
    return _accessible_department_ids(user)


def _accessible_department_ids(user):
    accesses = user.department_accesses.select_related("department")
    department_ids = set()
    for access in accesses:
        department_ids.add(access.department_id)
        if access.include_children:
            department_ids.update(_department_descendant_ids(access.department))
    return department_ids


def _department_descendant_ids(root):
    ids = set()
    queue = [root.id]
    children = list(Department.objects.values_list("id", "parent_id"))
    while queue:
        current_id = queue.pop()
        for department_id, parent_id in children:
            if parent_id == current_id and department_id not in ids:
                ids.add(department_id)
                queue.append(department_id)
    return ids
