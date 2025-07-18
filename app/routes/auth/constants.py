from werkzeug.security import generate_password_hash

ADMIN_USER = {
    'username': 'admin',
    'password_hash': generate_password_hash('password123')  # Пароль: password123
}

LOCATIONS = [
    {"name": "Невьянск", "coords": (57.491225, 60.218251), "color": "#FFCCCB"},
    {"name": "Кировград", "coords": (57.431916, 60.062321), "color": "#CBFFCC"},
    {"name": "Верх-Нейвинский", "coords": (57.265589, 60.131644), "color": "#CCCBFF"},
    {"name": "Арамиль", "coords": (56.700276, 60.828647), "color": "#FFFFCB"},
    {"name": "Нижняя Салда", "coords": (58.071490, 60.716331), "color": "#FFCBFF"},
    {"name": "Нижний Тагил", "coords": (57.907562, 59.971474), "color": "#FFD8CB"},
    {"name": "Верхняя Салда", "coords": (58.050898, 60.546253), "color": "#CBFFD8"},
    {"name": "Сысерть", "coords": (56.502286, 60.810034), "color": "#D8CBFF"},
    {"name": "Верхняя Сысерть", "coords": (56.438030, 60.755165), "color": "#FFEECB"},
    {"name": "с. Черданцево", "coords": (56.600331, 60.946263), "color": "#CBEEFF"},
    {"name": "д. Токарево", "coords": (56.613470, 60.947746), "color": "#EECBFF"},
    {"name": "Первоуральск", "coords": (56.905819, 59.943267), "color": "#CBFFEE"}
]