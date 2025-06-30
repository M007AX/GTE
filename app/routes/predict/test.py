import requests
import pandas as pd
from datetime import datetime, timedelta


def get_tomorrow_weather():
    # Определяем завтрашнюю дату
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    # Координаты для Екатеринбурга (UTC+5)
    latitude = 56.50
    longitude = 60.35

    # Делаем запрос к API
    url = 'https://api.open-meteo.com/v1/forecast'
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'hourly': 'temperature_2m,relativehumidity_2m,pressure_msl',
        'start_date': tomorrow_date,
        'end_date': tomorrow_date,
        'timezone': 'Asia/Yekaterinburg'
    }

    response = requests.get(url, params=params)
    data = response.json()

    # Создаем таблицу с данными
    weather_data = pd.DataFrame({
        'Час': [f'{i:02d}:00' for i in range(24)],
        'Температура (°C)': data['hourly']['temperature_2m'],
        'Давление (гПа)': data['hourly']['pressure_msl'],
        'Влажность (%)': data['hourly']['relativehumidity_2m']
    })

    return weather_data, tomorrow_date


# Получаем прогноз
tomorrow_forecast, date = get_tomorrow_weather()
print(f"Прогноз на завтра ({date}):")
print(tomorrow_forecast.to_string(index=False))  # Вывод без индексов