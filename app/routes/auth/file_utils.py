import pandas as pd
from flask import flash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from .constants import LOCATIONS
from .date_utils import parse_date

ALLOWED_EXTENSIONS = {'csv'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def process_weather_file(file):
    try:
        # Попробуем разные кодировки, если основная не сработает
        encodings = ['utf-8', 'windows-1251', 'cp1252']

        for encoding in encodings:
            try:
                # Читаем CSV файл, пропуская возможные пустые строки
                df = pd.read_csv(file, encoding=encoding, skip_blank_lines=True)

                # Проверяем, что файл не пустой
                if df.empty:
                    raise ValueError("Файл не содержит данных")

                # Проверяем необходимые колонки
                required_columns = ['Час']
                for loc in LOCATIONS:
                    required_columns.extend([
                        f"{loc['name']}_temp",
                        f"{loc['name']}_humidity",
                        f"{loc['name']}_pressure",
                        f"{loc['name']}_wind"
                    ])

                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    raise ValueError(f"Отсутствуют необходимые колонки: {missing_columns}")

                # Преобразуем данные
                weather_data = []
                for _, row in df.iterrows():
                    hour = row['Час']
                    for loc in LOCATIONS:
                        weather_data.append({
                            'Локация': loc['name'],
                            'Цвет': loc['color'],
                            'Час': hour,
                            'Температура (°C)': row[f"{loc['name']}_temp"],
                            'Влажность (%)': row[f"{loc['name']}_humidity"],
                            'Давление (гПа)': row[f"{loc['name']}_pressure"],
                            'Скорость ветра (м/с)': row[f"{loc['name']}_wind"]
                        })

                # Возвращаем данные без даты, так как дата берется из URL
                return weather_data, None

            except UnicodeDecodeError:
                continue

        raise ValueError("Не удалось прочитать файл. Проверьте кодировку и формат.")

    except Exception as e:
        raise ValueError(f'Ошибка обработки файла: {str(e)}')