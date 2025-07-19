from flask import render_template, redirect, session, flash, request, url_for, Blueprint, jsonify
from werkzeug.utils import secure_filename
from .file_utils import allowed_file, process_weather_file
from .date_utils import get_date_info, parse_date, get_tomorrow_date
from .constants import LOCATIONS
import os
import pandas as pd

from .model_utils import prepare_features, MODEL

project_bp = Blueprint('project', __name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@project_bp.route('/project', methods=['GET', 'POST'])
def project():
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    # Получаем дату по умолчанию (завтра)
    default_date = get_tomorrow_date()
    date_info = get_date_info(default_date)
    weather_data = None

    if request.method == 'POST':
        if 'weather_file' not in request.files:
            flash('Не выбран файл', 'error')
            return redirect(request.url)

        file = request.files['weather_file']
        if file.filename == '':
            flash('Не выбран файл', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            try:
                # Перемотка файла в начало на случай повторного чтения
                file.seek(0)
                weather_data, forecast_date = process_weather_file(file)
                if weather_data:
                    date_info = get_date_info(parse_date(forecast_date))
                    flash('Файл успешно загружен', 'success')
            except Exception as e:
                flash(f'Ошибка обработки файла: {str(e)}', 'error')

    return render_template('project.html',
                           weather_data=weather_data,
                           locations=LOCATIONS,
                           date_info=date_info)


@project_bp.route('/predict')
def predict():
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    try:
        # 1. Проверяем наличие загруженных данных
        # Создаем путь с папкой для завтрашней даты
        tomorrow_folder = get_tomorrow_date().strftime('%d.%m.%Y')
        date_folder = os.path.join(UPLOAD_FOLDER, tomorrow_folder)
        current_path = os.path.join(date_folder, 'features_table.csv')

        if not os.path.exists(current_path):
            flash('Сначала загрузите данные о погоде', 'error')
            return redirect(url_for('project.project'))

        # 2. Загружаем данные
        df = pd.read_csv(current_path)

        # 3. Подготавливаем фичи и делаем предсказания
        X = prepare_features(df)
        predictions = MODEL.predict(X)

        # 4. Сохраняем предсказания в CSV
        predictions_df = pd.DataFrame({
            'hour': range(24),
            'prediction': predictions
        })
        predictions_path = os.path.join(date_folder, 'predicted.csv')
        predictions_df.to_csv(predictions_path, index=False)

        # 5. Форматируем результат для отображения
        results = [{
            'hour': hour,
            'prediction': round(float(pred), 2)
        } for hour, pred in zip(range(24), predictions)]

        return render_template('predict.html', predictions=results)

    except Exception as e:
        flash(f'Ошибка при прогнозировании: {str(e)}', 'error')
        return redirect(url_for('project.project'))


@project_bp.route('/save-weather-data', methods=['POST'])
def save_weather_data():
    if not session.get('logged_in'):
        return {"success": False, "error": "Требуется авторизация"}, 401

    try:
        data = request.get_json()  # Получаем JSON-данные
        if not data:
            return {"success": False, "error": "Нет данных"}, 400

        # Создаем папку с датой
        tomorrow_folder = get_tomorrow_date().strftime('%d.%m.%Y')
        date_folder = os.path.join(UPLOAD_FOLDER, tomorrow_folder)
        os.makedirs(date_folder, exist_ok=True)

        # Сохраняем CSV в папку с датой
        csv_path = os.path.join(date_folder, 'features_table.csv')
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write(data['csv'])

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}, 500