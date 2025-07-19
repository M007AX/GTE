from flask import render_template, redirect, session, flash, request, url_for, Blueprint, jsonify
from werkzeug.utils import secure_filename
from .file_utils import allowed_file, process_weather_file
from .date_utils import get_date_info, parse_date, get_tomorrow_date
from .constants import LOCATIONS
import os
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .model_utils import prepare_features, MODEL, calculate_wape

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

    # Проверяем наличие сохранённых данных для этой даты
    date_folder = os.path.join(UPLOAD_FOLDER, default_date.strftime('%d.%m.%Y'))
    csv_path = os.path.join(date_folder, 'features_table.csv')

    if os.path.exists(csv_path):
        try:
            # Загружаем данные из CSV
            df = pd.read_csv(csv_path)

            # Преобразуем данные в формат, совместимый с шаблоном
            weather_data = []
            for _, row in df.iterrows():
                for loc in LOCATIONS:
                    loc_name = loc['name']
                    weather_data.append({
                        'Локация': loc_name,
                        'Час': f"{int(row['Час']):02d}:00",
                        'Температура (°C)': row[f"{loc_name}_temp"],
                        'Влажность (%)': row[f"{loc_name}_humidity"],
                        'Давление (гПа)': row[f"{loc_name}_pressure"],
                        'Скорость ветра (м/с)': row[f"{loc_name}_wind"]
                    })

            flash('Данные успешно загружены из сохранённого файла', 'success')
        except Exception as e:
            flash(f'Ошибка загрузки сохранённых данных: {str(e)}', 'error')

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
                file.seek(0)
                weather_data, forecast_date = process_weather_file(file)
                if weather_data:
                    date_info = get_date_info(parse_date(forecast_date))

                    date_folder = os.path.join(UPLOAD_FOLDER, forecast_date)
                    os.makedirs(date_folder, exist_ok=True)

                    save_data = []
                    for hour in range(24):
                        hour_str = f"{hour:02d}:00"
                        hour_data = {
                            'Час': hour,
                            'День_недели': date_info['day_of_week'],
                            'Неделя_года': date_info['week_of_year'],
                            'Рабочий_день': date_info['is_workday']
                        }

                        for loc in LOCATIONS:
                            loc_name = loc['name']
                            loc_hour_data = next((item for item in weather_data
                                                  if item['Локация'] == loc_name
                                                  and item['Час'] == hour_str), None)
                            if loc_hour_data:
                                hour_data.update({
                                    f"{loc_name}_temp": loc_hour_data['Температура (°C)'],
                                    f"{loc_name}_humidity": loc_hour_data['Влажность (%)'],
                                    f"{loc_name}_pressure": loc_hour_data['Давление (гПа)'],
                                    f"{loc_name}_wind": loc_hour_data['Скорость ветра (м/с)']
                                })
                            else:
                                hour_data.update({
                                    f"{loc_name}_temp": 0,
                                    f"{loc_name}_humidity": 0,
                                    f"{loc_name}_pressure": 0,
                                    f"{loc_name}_wind": 0
                                })
                        save_data.append(hour_data)

                    df = pd.DataFrame(save_data)
                    csv_path = os.path.join(date_folder, 'features_table.csv')
                    df.to_csv(csv_path, index=False, encoding='utf-8')

                    flash('Файл успешно загружен и данные сохранены', 'success')
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


@project_bp.route('/analysis', methods=['GET', 'POST'])
def analysis():
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    try:
        # 1. Проверяем наличие прогноза
        tomorrow_folder = get_tomorrow_date().strftime('%d.%m.%Y')
        date_folder = os.path.join(UPLOAD_FOLDER, tomorrow_folder)
        predicted_path = os.path.join(date_folder, 'predicted.csv')
        fact_path = os.path.join(date_folder, 'fact.csv')

        predicted = None
        actual = None
        combined_data = []
        metrics = None

        # Загружаем прогнозируемые данные если они есть
        if os.path.exists(predicted_path):
            predicted_df = pd.read_csv(predicted_path)
            predicted = [{
                'hour': row['hour'],
                'prediction': row['prediction']
            } for _, row in predicted_df.iterrows()]

        # Обработка загрузки файла с фактическими данными
        if request.method == 'POST':
            if 'fact_file' not in request.files:
                flash('Не выбран файл', 'error')
                return redirect(url_for('project.analysis'))

            file = request.files['fact_file']
            if file.filename == '':
                flash('Не выбран файл', 'error')
                return redirect(url_for('project.analysis'))

            if file and allowed_file(file.filename):
                try:
                    # Сохраняем файл с фактами
                    os.makedirs(date_folder, exist_ok=True)
                    file.save(fact_path)
                    flash('Фактические данные успешно загружены', 'success')
                except Exception as e:
                    flash(f'Ошибка сохранения файла: {str(e)}', 'error')

        # Если есть оба файла (прогноз и факт)
        if os.path.exists(fact_path) and os.path.exists(predicted_path):
            actual_df = pd.read_csv(fact_path)
            predicted_df = pd.read_csv(predicted_path)

            # Проверяем, что данные загружены корректно
            if not actual_df.empty and not predicted_df.empty:
                actual = [{
                    'hour': row['hour'],
                    'consumption': row['consumption']
                } for _, row in actual_df.iterrows()]

                # Подготавливаем объединенные данные для таблицы
                for hour in range(24):
                    # Получаем данные прогноза
                    pred_row = predicted_df[predicted_df['hour'] == hour].iloc[0] if not predicted_df[
                        predicted_df['hour'] == hour].empty else None

                    # Получаем фактические данные
                    actual_row = actual_df[actual_df['hour'] == hour].iloc[0] if not actual_df[
                        actual_df['hour'] == hour].empty else None

                    if pred_row is not None and actual_row is not None:
                        item = {
                            'hour': hour,
                            'prediction': pred_row['prediction'],
                            'actual': actual_row['consumption'],
                            'difference': actual_row['consumption'] - pred_row['prediction'],
                            'percentage_diff': ((actual_row['consumption'] - pred_row['prediction']) / actual_row[
                                'consumption']) * 100 if actual_row['consumption'] != 0 else 0
                        }
                        combined_data.append(item)

                # Вычисляем метрики качества
                y_true = actual_df['consumption']
                y_pred = predicted_df['prediction']

                metrics = {
                    'mae': mean_absolute_error(y_true, y_pred),
                    'rmse': mean_squared_error(y_true, y_pred),
                    'r2': r2_score(y_true, y_pred),
                    'wape': calculate_wape(y_true, y_pred)
                }

        return render_template('analysis.html',
                               predicted=predicted,
                               actual=actual,
                               combined_data=combined_data,
                               metrics=metrics)

    except Exception as e:
        flash(f'Ошибка при анализе данных: {str(e)}', 'error')
        return redirect(url_for('project.project'))