from datetime import datetime, date
import pytz
from typing import Dict, Any
from datetime import datetime, timedelta

# Универсальные праздники (без учета года)
UNIVERSAL_HOLIDAYS = [
    # Фиксированные даты
    ("01.01", "Новый год"),
    ("02.01", "Новый год"),
    ("03.01", "Новый год"),
    ("04.01", "Новый год"),
    ("05.01", "Новый год"),
    ("06.01", "Новый год"),
    ("07.01", "Рождество"),
    ("08.01", "Новый год"),
    ("23.02", "День защитника Отечества"),
    ("08.03", "Международный женский день"),
    ("01.05", "Праздник весны и труда"),
    ("09.05", "День Победы"),
    ("12.06", "День России"),
    ("04.11", "День народного единства"),

    # Праздники с плавающей датой (можно добавить вычисляемые, например Пасху)
]


def is_holiday(check_date: date) -> bool:
    """Проверяет, является ли дата праздничным днем"""
    date_str = check_date.strftime("%d.%m")

    # Проверяем фиксированные праздники
    for holiday_date, _ in UNIVERSAL_HOLIDAYS:
        if date_str == holiday_date:
            return True

    return False


def get_date_info(target_date: date) -> Dict[str, Any]:
    """Возвращает информацию о дате"""
    return {
        'day_of_week': target_date.weekday(),  # 0-6 (пн-вс)
        'week_of_year': target_date.isocalendar()[1],
        'is_workday': 1 if is_workday(target_date) else 0,  # 1 - рабочий, 0 - нет
        'date': target_date.strftime('%d.%m.%Y')
    }


def is_workday(target_date: date) -> bool:
    """Определяет, является ли день рабочим"""
    # Если это выходной (суббота или воскресенье)
    if target_date.weekday() >= 5:
        # И не праздник (праздничные выходные)
        return False

    # Если это будний день, но праздник
    if is_holiday(target_date):
        return False

    return True


def parse_date(date_str: str, date_format: str = '%d.%m.%Y') -> date:
    """Парсит строку с датой в объект date"""
    return datetime.strptime(date_str, date_format).date()


def get_tomorrow_date(timezone: str = 'Asia/Yekaterinburg') -> date:
    """Возвращает дату завтрашнего дня для указанного часового пояса"""
    tz = pytz.timezone(timezone)
    return (datetime.now(tz) + timedelta(days=1)).date()