from datetime import date, datetime, time, timedelta
from decimal import Decimal
import random

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.utils import timezone

from hr.models import (
    AuditLog,
    Campaign,
    CampaignRecord,
    ChangeLog,
    Contract,
    Department,
    Employee,
    EmployeeColumnPreference,
    Position,
    Probation,
)


class Command(BaseCommand):
    help = "Reset and create deterministic demo data for the HR Control Panel."

    def handle(self, *args, **options):
        rng = random.Random(20260619)
        today = date(2026, 6, 19)

        self._clear_data()
        users = self._create_roles_and_users()
        departments = self._create_departments()
        positions = self._create_positions()
        employees = self._create_employees(rng, today, departments, positions)
        self._assign_managers(rng, employees)
        self._create_probations(today, employees)
        self._create_campaigns(rng, today, employees)
        self._create_change_logs(rng, today, employees, users)

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data created: {len(employees)} employees, "
                f"{Department.objects.count()} departments, "
                f"{Campaign.objects.count()} campaigns."
            )
        )

    def _clear_data(self):
        for model in [
            CampaignRecord,
            Campaign,
            Probation,
            Contract,
            EmployeeColumnPreference,
            AuditLog,
            ChangeLog,
            Employee,
            Department,
            Position,
        ]:
            model.objects.all().delete()

    def _create_roles_and_users(self):
        group_names = ["HR Admin", "HR Manager", "HR Viewer"]
        for name in group_names:
            Group.objects.filter(name=name).delete()

        User = get_user_model()
        User.objects.filter(username__in=["hr_admin", "hr_manager", "hr_viewer"]).delete()

        admin_group = Group.objects.create(name="HR Admin")
        manager_group = Group.objects.create(name="HR Manager")
        viewer_group = Group.objects.create(name="HR Viewer")

        hr_permissions = list(Permission.objects.filter(content_type__app_label="hr"))
        user_permissions = list(
            Permission.objects.filter(
                content_type__app_label="auth",
                content_type__model="user",
                codename__in=["view_user", "add_user", "change_user"],
            )
        )
        admin_group.permissions.set(hr_permissions + user_permissions)

        manager_permissions = [
            permission
            for permission in hr_permissions
            if permission.codename.startswith(("view_", "add_", "change_"))
        ]
        manager_group.permissions.set(manager_permissions)

        viewer_permissions = [
            permission
            for permission in hr_permissions
            if permission.codename.startswith("view_")
        ]
        viewer_group.permissions.set(viewer_permissions)

        admin = User.objects.create_user(
            username="hr_admin",
            password="Admin12345!",
            email="hr_admin@example.test",
            first_name="HR",
            last_name="Admin",
            is_staff=True,
            is_superuser=True,
        )
        manager = User.objects.create_user(
            username="hr_manager",
            password="Manager12345!",
            email="hr_manager@example.test",
            first_name="HR",
            last_name="Manager",
        )
        viewer = User.objects.create_user(
            username="hr_viewer",
            password="Viewer12345!",
            email="hr_viewer@example.test",
            first_name="HR",
            last_name="Viewer",
        )
        admin.groups.add(admin_group)
        manager.groups.add(manager_group)
        viewer.groups.add(viewer_group)

        for user in [admin, manager, viewer]:
            EmployeeColumnPreference.objects.get_or_create(user=user)

        return {"admin": admin, "manager": manager, "viewer": viewer}

    def _create_departments(self):
        department_specs = [
            ("Компания", None),
            ("People & Culture", "Компания"),
            ("HR Operations", "People & Culture"),
            ("Talent Acquisition", "People & Culture"),
            ("Learning & Development", "People & Culture"),
            ("Finance", "Компания"),
            ("Accounting", "Finance"),
            ("Payroll", "Finance"),
            ("Product", "Компания"),
            ("Product Analytics", "Product"),
            ("UX Research", "Product"),
            ("Engineering", "Компания"),
            ("Backend Platform", "Engineering"),
            ("Frontend Platform", "Engineering"),
            ("QA Automation", "Engineering"),
            ("Data Office", "Engineering"),
            ("Sales", "Компания"),
            ("Enterprise Sales", "Sales"),
            ("SMB Sales", "Sales"),
            ("Customer Success", "Компания"),
            ("Support", "Customer Success"),
            ("Legal", "Компания"),
            ("Office Management", "Компания"),
        ]
        departments = {}
        for name, parent_name in department_specs:
            departments[name] = Department.objects.create(
                name=name,
                parent=departments.get(parent_name),
            )
        return departments

    def _create_positions(self):
        names = [
            "HR Business Partner",
            "HR Operations Specialist",
            "Recruiter",
            "People Partner",
            "Learning Manager",
            "Accountant",
            "Payroll Specialist",
            "Financial Analyst",
            "Product Manager",
            "Product Analyst",
            "UX Researcher",
            "Backend Developer",
            "Frontend Developer",
            "Fullstack Developer",
            "QA Engineer",
            "Data Engineer",
            "Data Analyst",
            "Engineering Manager",
            "Team Lead",
            "Sales Manager",
            "Account Executive",
            "Customer Success Manager",
            "Support Specialist",
            "Legal Counsel",
            "Office Manager",
            "Operations Director",
            "Compensation Analyst",
            "HR Data Analyst",
        ]
        return [Position.objects.create(name=name) for name in names]

    def _create_employees(self, rng, today, departments, positions):
        first_names = [
            "Алексей",
            "Мария",
            "Иван",
            "Екатерина",
            "Дмитрий",
            "Анна",
            "Сергей",
            "Ольга",
            "Никита",
            "Ксения",
            "Павел",
            "Виктория",
            "Роман",
            "Дарья",
            "Георгий",
            "Полина",
            "Артём",
            "Елена",
            "Максим",
            "София",
        ]
        last_names = [
            "Кирсанов",
            "Миронова",
            "Лесников",
            "Ветрова",
            "Савельев",
            "Орлова",
            "Ковалёв",
            "Назарова",
            "Беляев",
            "Соколова",
            "Фомин",
            "Егорова",
            "Зуев",
            "Киселёва",
            "Тихонов",
            "Рябова",
            "Маслов",
            "Громова",
            "Демин",
            "Синицына",
            "Иванов",
            "Иванов",
            "Смирнова",
            "Смирнова",
        ]
        middle_names = [
            "",
            "Андреевич",
            "Сергеевна",
            "Игоревич",
            "Павловна",
            "Викторович",
            "Олеговна",
            "Михайлович",
        ]
        department_list = list(departments.values())
        contract_types = [choice[0] for choice in Employee.CONTRACT_TYPE_CHOICES]
        ipr_statuses = [
            Employee.IPR_ACTUAL,
            Employee.IPR_ACTUAL,
            Employee.IPR_ACTUAL,
            Employee.IPR_NONE,
            Employee.IPR_EXPIRED,
            Employee.IPR_EXPIRING,
        ]
        dismissed_indices = set(rng.sample(range(20, 230), 8))

        edge_cases = [
            {
                "first_name": "Пётр",
                "last_name": "Беззарплатный",
                "middle_name": "",
                "email": "edge.salary@example.test",
                "salary_gross": None,
                "salary_net": None,
            },
            {
                "first_name": "Лина",
                "last_name": "Безпочтовая",
                "middle_name": "",
                "email": "",
            },
            {
                "first_name": "Олег",
                "last_name": "Безподразделения",
                "middle_name": "",
                "department": None,
            },
            {
                "first_name": "Кларисса",
                "last_name": "Длиннофамильная-Тестовая-Сверхдлинная",
                "middle_name": "Александровна",
                "email": "long.name@example.test",
            },
            {
                "first_name": "Алина",
                "last_name": "Иванова",
                "middle_name": "",
                "email": "same.last.1@example.test",
            },
            {
                "first_name": "Алиса",
                "last_name": "Иванова",
                "middle_name": "",
                "email": "same.last.2@example.test",
            },
            {
                "first_name": "Егор",
                "last_name": "НулеваяЗарплата",
                "middle_name": "",
                "salary_gross": Decimal("0"),
                "salary_net": Decimal("0"),
            },
            {
                "first_name": "Ренат",
                "last_name": "БольшаяЗарплата",
                "middle_name": "",
                "salary_gross": Decimal("2500000"),
                "salary_net": Decimal("2175000"),
            },
            {
                "first_name": "Марта",
                "last_name": "Евровалютная",
                "middle_name": "",
                "currency": "EUR",
                "salary_gross": Decimal("9200"),
                "salary_net": Decimal("6900"),
            },
            {
                "first_name": "Степан",
                "last_name": "ПросроченныйДоговор",
                "middle_name": "",
                "contract_end_date": today - timedelta(days=17),
            },
        ]

        employees = []
        for index in range(230):
            hire_date = self._random_date(rng, date(2024, 1, 10), date(2026, 6, 8))
            contract_end_date = self._contract_end_date(rng, today, index)
            is_active = index not in dismissed_indices
            dismissal_date = None
            if not is_active:
                dismissal_date = hire_date + timedelta(days=rng.randint(120, 680))
                if dismissal_date > today:
                    dismissal_date = today - timedelta(days=rng.randint(4, 90))

            currency = "EUR" if rng.random() < 0.12 else "RUB"
            salary_gross, salary_net = self._salary_pair(rng, currency)
            department = rng.choice(department_list)
            position = rng.choice(positions)
            first_name = rng.choice(first_names)
            last_name = rng.choice(last_names)
            middle_name = rng.choice(middle_names)
            email = f"employee{index + 1:03d}@example.test"

            if index % 31 == 0:
                email = ""
            if index % 37 == 0:
                middle_name = ""
            if index % 43 == 0:
                salary_gross = None
                salary_net = None
            if index % 47 == 0:
                department = None
            if index % 53 == 0:
                position = None

            payload = {
                "first_name": first_name,
                "last_name": last_name,
                "middle_name": middle_name,
                "email": email,
                "department": department,
                "position": position,
                "hire_date": hire_date,
                "dismissal_date": dismissal_date,
                "is_active": is_active,
                "ipr_status": rng.choice(ipr_statuses),
                "contract_type": rng.choice(contract_types),
                "contract_end_date": contract_end_date,
                "salary_gross": salary_gross,
                "salary_net": salary_net,
                "currency": currency,
            }
            if index < len(edge_cases):
                payload.update(edge_cases[index])
                payload.setdefault("department", department)
                payload.setdefault("position", position)

            employee = Employee.objects.create(**payload)
            Contract.objects.create(
                employee=employee,
                contract_type=employee.contract_type or Employee.CONTRACT_LABOR,
                end_date=employee.contract_end_date,
            )
            employees.append(employee)

        return employees

    def _random_date(self, rng, start, end):
        return start + timedelta(days=rng.randint(0, (end - start).days))

    def _contract_end_date(self, rng, today, index):
        if index % 23 == 0:
            return today - timedelta(days=rng.randint(1, 120))
        if index % 11 == 0:
            return today + timedelta(days=rng.randint(1, 30))
        if index % 41 == 0:
            return None
        return today + timedelta(days=rng.randint(31, 520))

    def _salary_pair(self, rng, currency):
        if currency == "EUR":
            gross = Decimal(rng.randrange(2400, 8300, 100))
            net = (gross * Decimal("0.75")).quantize(Decimal("1"))
            return gross, net
        gross = Decimal(rng.randrange(90000, 460000, 5000))
        net = (gross * Decimal("0.87")).quantize(Decimal("1"))
        return gross, net

    def _assign_managers(self, rng, employees):
        manager_pool = [employee for employee in employees[:45] if employee.is_active]
        for employee in employees:
            if employee in manager_pool or not employee.is_active:
                continue
            if rng.random() < 0.72:
                manager = rng.choice(manager_pool)
                if manager.pk != employee.pk:
                    employee.manager = manager
                    employee.save(update_fields=["manager"])

    def _create_probations(self, today, employees):
        specs = [
            (12, today - timedelta(days=104), today - timedelta(days=14), Probation.RESULT_FAILED, "Не достигнуты цели адаптации."),
            (13, today - timedelta(days=96), today - timedelta(days=6), Probation.RESULT_FAILED, "Ожидает финального оформления увольнения."),
            (14, today - timedelta(days=92), today - timedelta(days=2), Probation.RESULT_FAILED, "Решение принято руководителем."),
            (15, today - timedelta(days=82), today + timedelta(days=8), Probation.RESULT_PENDING, "Финальная встреча назначена."),
            (16, today - timedelta(days=55), today + timedelta(days=35), Probation.RESULT_PENDING, "Идёт второй месяц адаптации."),
            (17, today - timedelta(days=30), today + timedelta(days=60), Probation.RESULT_PENDING, ""),
            (18, today - timedelta(days=7), today + timedelta(days=83), Probation.RESULT_PENDING, "Новый сотрудник."),
            (19, today - timedelta(days=96), today - timedelta(days=6), Probation.RESULT_PASSED, "Испытательный срок закрыт успешно."),
            (20, today - timedelta(days=89), today + timedelta(days=1), Probation.RESULT_PENDING, "Финальная оценка завтра."),
            (21, today - timedelta(days=90), today, Probation.RESULT_PENDING, "Срок заканчивается сегодня."),
        ]
        for employee_index, start_date, end_date, result, comment in specs:
            employee = employees[employee_index]
            employee.hire_date = start_date
            employee.is_active = True
            employee.dismissal_date = None
            employee.save(update_fields=["hire_date", "is_active", "dismissal_date"])
            Probation.objects.create(
                employee=employee,
                start_date=start_date,
                end_date=end_date,
                week_1_done=start_date + timedelta(days=7) < today,
                month_1_done=start_date + timedelta(days=30) < today and employee_index != 14,
                middle_review_done=start_date + timedelta(days=45) < today and employee_index not in [13, 14],
                month_2_done=start_date + timedelta(days=60) < today and employee_index not in [12, 13, 14],
                final_review_done=result == Probation.RESULT_PASSED,
                final_survey_done=result == Probation.RESULT_PASSED,
                result=result,
                comment=comment,
            )

    def _create_campaigns(self, rng, today, employees):
        campaign_specs = [
            ("Весна", 2025, Campaign.STATUS_CLOSED, today - timedelta(days=450), today - timedelta(days=420), today - timedelta(days=390)),
            ("Осень", 2025, Campaign.STATUS_CLOSED, today - timedelta(days=250), today - timedelta(days=220), today - timedelta(days=190)),
            ("Зима", 2026, Campaign.STATUS_CLOSED, today - timedelta(days=140), today - timedelta(days=110), today - timedelta(days=80)),
            ("Весна", 2026, Campaign.STATUS_OPEN, today - timedelta(days=35), today - timedelta(days=5), None),
            ("Лето", 2026, Campaign.STATUS_OPEN, today + timedelta(days=8), today + timedelta(days=36), None),
            ("DM Review", 2026, Campaign.STATUS_OPEN, today - timedelta(days=10), today + timedelta(days=20), None),
        ]
        for season, year, status, start_date, apply_date, closed_at in campaign_specs:
            campaign = Campaign.objects.create(
                season=season,
                year=year,
                status=status,
                start_date=start_date,
                default_apply_date=apply_date,
                closed_at=closed_at,
            )
            sample_size = rng.randint(24, 42)
            for employee in rng.sample(employees, sample_size):
                record_status = (
                    rng.choice([CampaignRecord.STATUS_DONE, CampaignRecord.STATUS_CANCELLED])
                    if status == Campaign.STATUS_CLOSED
                    else rng.choice(
                        [
                            CampaignRecord.STATUS_ACTIVE,
                            CampaignRecord.STATUS_ACTIVE,
                            CampaignRecord.STATUS_DONE,
                        ]
                    )
                )
                CampaignRecord.objects.create(
                    campaign=campaign,
                    employee=employee,
                    status=record_status,
                    value=Decimal(rng.randrange(0, 25, 1)),
                    comment=rng.choice(
                        [
                            "",
                            "Ожидает калибровки.",
                            "Подтверждено руководителем.",
                            "Требуется дополнительная проверка.",
                        ]
                    ),
                )

    def _create_change_logs(self, rng, today, employees, users):
        events = [
            "Обновлён статус ИПР",
            "Изменён тип договора",
            "Обновлена зарплатная информация",
            "Назначен руководитель",
            "Добавлена запись кампании",
            "Изменён статус испытательного срока",
            "Обновлено подразделение",
        ]

        for index, employee in enumerate(employees[:80]):
            created_at = self._aware_datetime(today - timedelta(days=index % 28), 9 + index % 8)
            event = rng.choice(events)
            ChangeLog.objects.create(
                created_at=created_at,
                employee=employee,
                event=event,
            )
            if index < 35:
                AuditLog.objects.create(
                    created_at=created_at,
                    actor=users["manager"] if index % 3 else users["admin"],
                    action=AuditLog.ACTION_UPDATE,
                    model_name="Employee",
                    object_id=str(employee.pk),
                    object_repr=employee.full_name,
                    event=event,
                    before={"demo": "before"},
                    after={"demo": "after"},
                    ip_address="127.0.0.1",
                    path="/seed_demo_data/",
                )

        ChangeLog.objects.create(
            created_at=self._aware_datetime(today, 12),
            employee=None,
            event="Демо-данные пересозданы командой seed_demo_data",
        )
        AuditLog.objects.create(
            created_at=self._aware_datetime(today, 12),
            actor=users["admin"],
            action=AuditLog.ACTION_IMPORT,
            model_name="",
            object_id="",
            object_repr="",
            event="Демо-данные пересозданы командой seed_demo_data",
            after={"employees": len(employees)},
            ip_address="127.0.0.1",
            path="/seed_demo_data/",
        )

    def _aware_datetime(self, day, hour):
        return timezone.make_aware(datetime.combine(day, time(hour=hour, minute=0)))
