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

## Что уже работает

- Dashboard с реальными счётчиками, договорами на истечении и последними изменениями.
- Список сотрудников с поиском, фильтрами, сводкой по текущей выборке и деталкой.
- Создание, редактирование, увольнение и возврат сотрудников.
- Страница испытательного срока с кликабельными этапами и финализацией.
- Древовидные подразделения, создание/редактирование и CSV-выгрузка структуры.
- Месячный календарь с событиями из сотрудников, испытательного срока, ИПР и кампаний.
- Оценочные/DM-кампании, карточка кампании и добавление записей для сотрудников.
- Простые страницы дополнительного меню.
- Детерминированные демо-данные через `python manage.py seed_demo_data`.
