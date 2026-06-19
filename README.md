# HR Control Panel

MVP веб-приложения для панели управления сотрудниками на Django, SQLite,
Django Templates, HTML/CSS и Vanilla JavaScript.

## Запуск

```bash
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
```

После запуска откройте http://127.0.0.1:8000/.

Если используется не Windows, команды отличаются только активацией окружения:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
```

## Демо-пользователи

Команда `seed_demo_data` создаёт роли и пользователей:

- `hr_admin` / `Admin12345!` — полный доступ, staff/superuser.
- `hr_manager` / `Manager12345!` — чтение, создание и редактирование HR-данных.
- `hr_viewer` / `Viewer12345!` — только чтение и экспорт.

## Что уже работает

- Dashboard с реальными счётчиками, договорами на истечении и последними изменениями.
- Список сотрудников с поиском, фильтрами, сводкой по текущей выборке и деталкой.
- Создание, редактирование, увольнение и возврат сотрудников.
- Авторизация Django и роли через группы/permissions.
- Excel-экспорт текущей выборки сотрудников.
- Excel-импорт сотрудников с create/update по ID или email.
- Настройка видимых колонок и размера страницы для каждого пользователя.
- Пагинация списка сотрудников.
- Строгий audit log с пользователем, действием, объектом, IP, path и snapshot before/after.
- Страница испытательного срока с кликабельными этапами и финализацией.
- Древовидные подразделения, создание/редактирование и CSV-выгрузка структуры.
- Месячный календарь с событиями из сотрудников, испытательного срока, ИПР и кампаний.
- Оценочные/DM-кампании, карточка кампании и добавление записей для сотрудников.
- Простые страницы дополнительного меню.
- Детерминированные демо-данные через `python manage.py seed_demo_data`.

## Production-настройки

Без дополнительных библиотек настройки читаются из переменных окружения. Шаблон есть в
`.env.example`.

Минимальный набор для production:

```bash
set DJANGO_SECRET_KEY=replace-with-long-random-secret
set DJANGO_DEBUG=0
set DJANGO_ALLOWED_HOSTS=example.com,www.example.com
set DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
set DJANGO_SECURE_SSL_REDIRECT=1
set DJANGO_SESSION_COOKIE_SECURE=1
set DJANGO_CSRF_COOKIE_SECURE=1
set DJANGO_SECURE_HSTS_SECONDS=31536000
python manage.py collectstatic
```

## Тесты

```bash
python manage.py test
```

Покрыты auth redirect, запрет записи для viewer, настройки колонок и пагинация,
Excel export/import и audit snapshot при редактировании.
