from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pytz
import requests
import pandas as pd
from .date_utils import get_date_info, get_tomorrow_date, parse_date

auth_bp = Blueprint('auth', __name__)

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

@auth_bp.route('/')
def index():
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Заполните все поля', 'error')
            return redirect(url_for('auth.login'))

        if username != ADMIN_USER['username'] or not check_password_hash(ADMIN_USER['password_hash'], password):
            flash('Неверные учетные данные', 'error')
            return redirect(url_for('auth.login'))

        session['logged_in'] = True
        flash('Добро пожаловать!', 'success')
        return redirect(url_for('auth.project'))

    return render_template('auth/login.html')

def get_tomorrow_weather():
    """Получает прогноз погоды на завтра для всех локаций"""
    tomorrow_date = get_tomorrow_date()
    api_date = tomorrow_date.strftime('%Y-%m-%d')
    display_date = tomorrow_date.strftime('%d.%m.%Y')

    all_weather = []

    for loc in LOCATIONS:
        try:
            response = requests.get(
                'https://api.open-meteo.com/v1/forecast',
                params={
                    'latitude': loc['coords'][0],
                    'longitude': loc['coords'][1],
                    'hourly': 'temperature_2m,relativehumidity_2m,pressure_msl,windspeed_10m',
                    'start_date': api_date,
                    'end_date': api_date,
                    'timezone': 'Asia/Yekaterinburg'
                }
            )
            response.raise_for_status()
            data = response.json()

            for hour in range(24):
                all_weather.append({
                    'Локация': loc['name'],
                    'Цвет': loc['color'],
                    'Час': f'{hour:02d}:00',
                    'Температура (°C)': data['hourly']['temperature_2m'][hour],
                    'Влажность (%)': data['hourly']['relativehumidity_2m'][hour],
                    'Давление (гПа)': data['hourly']['pressure_msl'][hour],
                    'Скорость ветра (м/с)': data['hourly']['windspeed_10m'][hour]
                })

        except requests.exceptions.RequestException as e:
            flash(f'Ошибка при получении данных для {loc["name"]}: {str(e)}', 'error')
            continue

    return all_weather, display_date

@auth_bp.route('/project')
def project():
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    weather_data, forecast_date = get_tomorrow_weather()
    date_info = get_date_info(parse_date(forecast_date))

    return render_template('project.html',
                         weather_data=weather_data,
                         forecast_date=forecast_date,
                         locations=LOCATIONS,
                         date_info=date_info)

@auth_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/save-weather-data', methods=['POST'])
def save_weather_data():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401

    try:
        data = request.get_json()
        changes = data.get('changes', [])

        # Здесь должна быть логика сохранения изменений в ваше хранилище данных
        # Например, обновление weather_data или запись в базу данных

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500