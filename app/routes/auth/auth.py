from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pytz
import requests
import pandas as pd

auth_bp = Blueprint('auth', __name__)

ADMIN_USER = {
    'username': 'admin',
    'password_hash': generate_password_hash('password123')  # Пароль: password123
}


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
    """Получает прогноз погоды на завтра для Екатеринбурга"""
    ekb_tz = pytz.timezone('Asia/Yekaterinburg')
    now_ekb = datetime.now(ekb_tz)

    tomorrow_date = (now_ekb + timedelta(days=1)).strftime('%d.%m.%Y')
    api_date = (now_ekb + timedelta(days=1)).strftime('%Y-%m-%d')

    try:
        response = requests.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude': 56.50,
                'longitude': 60.35,
                'hourly': 'temperature_2m,relativehumidity_2m,pressure_msl',
                'start_date': api_date,
                'end_date': api_date,
                'timezone': 'Asia/Yekaterinburg'
            }
        )
        response.raise_for_status()
        data = response.json()

        weather_df = pd.DataFrame({
            'W, kW': [None] * 24,
            'Час': [f'{i:02d}:00' for i in range(24)],
            'Температура (°C)': data['hourly']['temperature_2m'],
            'Влажность (%)': data['hourly']['relativehumidity_2m'],
            'Давление (гПа)': data['hourly']['pressure_msl']
        })

        return weather_df, tomorrow_date

    except requests.exceptions.RequestException as e:
        flash(f'Ошибка при получении данных о погоде: {str(e)}', 'error')
        empty_df = pd.DataFrame(columns=['W, kW', 'Час', 'Температура (°C)', 'Влажность (%)', 'Давление (гПа)'])
        return empty_df, tomorrow_date


@auth_bp.route('/project')
def project():
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    utc_now = datetime.utcnow()
    ekaterinburg_tz = pytz.timezone('Asia/Yekaterinburg')
    now_ekb = utc_now.replace(tzinfo=pytz.utc).astimezone(ekaterinburg_tz)

    weather_df, forecast_date = get_tomorrow_weather()

    # Преобразуем DataFrame в список словарей для удобного использования в шаблоне
    weather_records = weather_df.to_dict('records')

    return render_template('project.html',
                           now=now_ekb,
                           timedelta=timedelta,
                           weather_records=weather_records,
                           forecast_date=forecast_date)


@auth_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('auth.login'))