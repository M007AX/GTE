from flask import render_template, redirect, session, flash, request, url_for
from werkzeug.utils import secure_filename
from .auth_routes import auth_bp
from .file_utils import allowed_file, process_weather_file
from .date_utils import get_date_info, parse_date, get_tomorrow_date
from .constants import LOCATIONS
import os
import pandas as pd

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@auth_bp.route('/project', methods=['GET', 'POST'])
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


@auth_bp.route('/predict')
def predict():
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    try:
        # 1. Проверяем наличие загруженных данных
        current_path = os.path.join(UPLOAD_FOLDER, 'current_weather.csv')
        if not os.path.exists(current_path):
            flash('Сначала загрузите данные о погоде', 'error')
            return redirect(url_for('auth.project'))

        # 2. Загружаем данные
        df = pd.read_csv(current_path)

        # 3. Подготавливаем фичи и делаем предсказания
        X = prepare_features(df)
        predictions = MODEL.predict(X)

        # 4. Форматируем результат
        results = [{
            'hour': hour,
            'prediction': round(float(pred), 2)
        } for hour, pred in zip(range(24), predictions)]

        return render_template('predict.html', predictions=results)

    except Exception as e:
        flash(f'Ошибка при прогнозировании: {str(e)}', 'error')
        return redirect(url_for('auth.project'))