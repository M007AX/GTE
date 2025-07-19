import joblib
import numpy as np
import os
import pandas as pd
from pathlib import Path
from .constants import LOCATIONS

# Получаем абсолютный путь к директории с auth.py
current_dir = Path(__file__).parent
MODEL_PATH = current_dir / 'xgboost_model.joblib'

# Проверяем существование файла
if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Model file not found at {MODEL_PATH}")

# Загружаем модель
MODEL = joblib.load(MODEL_PATH)

def prepare_features(weather_df):
    """Подготовка фичей для модели с проверкой данных"""
    features = []

    # Проверяем наличие всех необходимых столбцов
    required_columns = ['Час', 'День_недели', 'Неделя_года', 'Рабочий_день']
    for loc in LOCATIONS:
        required_columns.extend([
            f"{loc['name']}_temp",
            f"{loc['name']}_humidity",
            f"{loc['name']}_pressure",
            f"{loc['name']}_wind"
        ])

    missing_columns = [col for col in required_columns if col not in weather_df.columns]
    if missing_columns:
        raise ValueError(f"Отсутствуют необходимые столбцы: {missing_columns}")

    # Заменяем пропущенные значения (если есть '-')
    weather_df = weather_df.replace('-', np.nan)
    weather_df = weather_df.fillna(0)  # Или другое подходящее значение

    for hour in range(24):
        # Получаем данные для текущего часа
        current_hour = hour + 1 if hour < 23 else 0
        hour_data = weather_df[weather_df['Час'] == current_hour]

        if hour_data.empty:
            features.append([0] * len(required_columns))  # Заполняем нулями, если нет данных
            continue

        # Собираем фичи в правильном порядке
        hour_feat = [
            hour_data['Час'].values[0],
            hour_data['День_недели'].values[0],
            hour_data['Неделя_года'].values[0],
            hour_data['Рабочий_день'].values[0]
        ]

        # Добавляем погодные данные для всех локаций
        for loc in LOCATIONS:
            hour_feat += [
                hour_data[f"{loc['name']}_temp"].values[0],
                hour_data[f"{loc['name']}_humidity"].values[0],
                hour_data[f"{loc['name']}_pressure"].values[0],
                hour_data[f"{loc['name']}_wind"].values[0]
            ]

        features.append(hour_feat)

    return np.array(features)


def calculate_wape(y_true, y_pred):
    """
    Рассчитывает взвешенную абсолютную процентную ошибку (WAPE)

    Параметры:
    y_true - фактические значения (массив или список)
    y_pred - предсказанные значения (массив или список)

    Возвращает:
    WAPE в процентах
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    absolute_errors = np.abs(y_true - y_pred)
    sum_absolute_errors = np.sum(absolute_errors)
    sum_actual_values = np.sum(y_true)

    return (sum_absolute_errors / sum_actual_values) * 100 if sum_actual_values != 0 else 0