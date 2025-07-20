from flask import render_template, redirect, session, flash, request, url_for, Blueprint, jsonify
from werkzeug.utils import secure_filename
from .file_utils import allowed_file, process_weather_file
from .date_utils import get_date_info, parse_date, get_tomorrow_date
from .constants import LOCATIONS
import os
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from datetime import datetime
from .model_utils import prepare_features, MODEL, calculate_wape

project_bp = Blueprint('project', __name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@project_bp.route('/project')
def project_redirect():
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    # Перенаправляем на завтрашнюю дату по умолчанию
    tomorrow = get_tomorrow_date().strftime('%d-%m-%Y')
    return redirect(url_for('project.project', date_str=tomorrow))


@project_bp.route('/project/<date_str>', methods=['GET', 'POST'])
def project(date_str):
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    try:
        target_date = parse_date(date_str, '%d-%m-%Y')
    except ValueError:
        flash('Некорректный формат даты. Используйте DD-MM-YYYY', 'error')
        return redirect(url_for('project.project_redirect'))

    date_info = get_date_info(target_date)
    weather_data = None

    # Проверяем наличие сохранённых данных
    date_folder = os.path.join(UPLOAD_FOLDER, target_date.strftime('%d.%m.%Y'))
    csv_path = os.path.join(date_folder, 'features_table.csv')

    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            weather_data = []
            for _, row in df.iterrows():
                for loc in LOCATIONS:
                    loc_name = loc['name']
                    hour = int(row['Час'])
                    display_hour = hour - 1 if hour > 0 else 23  # Преобразуем для отображения 0-23
                    weather_data.append({
                        'Локация': loc_name,
                        'Час': f"{display_hour:02d}:00",
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
            return redirect(url_for('project.project', date_str=date_str))

        file = request.files['weather_file']
        if file and allowed_file(file.filename):
            try:
                file.seek(0)
                weather_data, _ = process_weather_file(file)
                if weather_data:
                    os.makedirs(date_folder, exist_ok=True)
                    save_data = []

                    # Сохраняем часы в порядке 1,2,...,23,0
                    for hour in range(24):
                        display_hour = hour  # Для отображения 0-23
                        save_hour = hour + 1 if hour < 23 else 0  # Для сохранения 1,2,...,23,0

                        hour_data = {
                            'Час': save_hour,  # Сохраняем в нужном для модели формате
                            'День_недели': date_info['day_of_week'],
                            'Неделя_года': date_info['week_of_year'],
                            'Рабочий_день': date_info['is_workday']
                        }

                        hour_str = f"{display_hour:02d}:00"
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
                    df.to_csv(csv_path, index=False, encoding='utf-8')
                    flash('Файл успешно загружен и данные сохранены', 'success')
                    return redirect(url_for('project.project', date_str=date_str))
            except Exception as e:
                flash(f'Ошибка обработки файла: {str(e)}', 'error')

    return render_template('project.html',
                           weather_data=weather_data,
                           locations=LOCATIONS,
                           date_info=date_info)


@project_bp.route('/predict')
def predict_redirect():
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    # Перенаправляем на завтрашнюю дату по умолчанию
    tomorrow = get_tomorrow_date().strftime('%d-%m-%Y')
    return redirect(url_for('project.predict', date_str=tomorrow))


@project_bp.route('/predict/<date_str>')
def predict(date_str):
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    try:
        # Парсим дату из URL
        target_date = parse_date(date_str, '%d-%m-%Y')
        date_folder = os.path.join(UPLOAD_FOLDER, target_date.strftime('%d.%m.%Y'))
        csv_path = os.path.join(date_folder, 'features_table.csv')

        if not os.path.exists(csv_path):
            flash('Сначала загрузите данные о погоде', 'error')
            return redirect(url_for('project.project', date_str=date_str))

        # Загружаем данные
        df = pd.read_csv(csv_path)

        # Подготавливаем фичи и делаем предсказания
        X = prepare_features(df)
        predictions = MODEL.predict(X)

        # Сохраняем предсказания
        predictions_df = pd.DataFrame({
            'hour': range(24),
            'prediction': predictions
        })
        predictions_path = os.path.join(date_folder, 'predicted.csv')
        predictions_df.to_csv(predictions_path, index=False)

        # Форматируем результат
        results = [{
            'hour': hour,
            'prediction': round(float(pred), 2)
        } for hour, pred in zip(range(24), predictions)]

        return render_template('predict.html',
                               predictions=results,
                               date_info=get_date_info(target_date))

    except ValueError:
        flash('Некорректный формат даты', 'error')
        return redirect(url_for('project.predict_redirect'))
    except Exception as e:
        flash(f'Ошибка при прогнозировании: {str(e)}', 'error')
        return redirect(url_for('project.project_redirect'))


@project_bp.route('/save-weather-data', methods=['POST'])
def save_weather_data():
    if not session.get('logged_in'):
        return {"success": False, "error": "Требуется авторизация"}, 401

    try:
        data = request.get_json()
        if not data:
            return {"success": False, "error": "Нет данных"}, 400

        # Получаем дату из данных
        date_str = data.get('date')
        if not date_str:
            return {"success": False, "error": "Не указана дата"}, 400

        # Создаем папку с датой
        date_folder = os.path.join(UPLOAD_FOLDER, date_str)
        os.makedirs(date_folder, exist_ok=True)

        # Сохраняем CSV в папку с датой
        csv_path = os.path.join(date_folder, 'features_table.csv')
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write(data['csv'])

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


@project_bp.route('/analysis')
def analysis_redirect():
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    # Перенаправляем на завтрашнюю дату по умолчанию
    tomorrow = get_tomorrow_date().strftime('%d-%m-%Y')
    return redirect(url_for('project.analysis', date_str=tomorrow))


@project_bp.route('/analysis/<date_str>', methods=['GET', 'POST'])
def analysis(date_str):
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))

    error = None
    predicted = None
    actual = None
    combined_data = []
    metrics = None
    date_info = None

    try:
        # Парсим дату из URL
        target_date = parse_date(date_str, '%d-%m-%Y')
        date_info = get_date_info(target_date)
        date_folder = os.path.join(UPLOAD_FOLDER, target_date.strftime('%d.%m.%Y'))
        predicted_path = os.path.join(date_folder, 'predicted.csv')
        fact_path = os.path.join(date_folder, 'fact.csv')

        # Загружаем прогнозируемые данные если они есть
        if os.path.exists(predicted_path):
            predicted_df = pd.read_csv(predicted_path)
            # Конвертируем numpy типы в нативные Python типы
            predicted = [{
                'hour': int(row['hour']),
                'prediction': float(row['prediction'])
            } for _, row in predicted_df.iterrows()]

        # Обработка загрузки файла с фактическими данными
        if request.method == 'POST':
            if 'fact_file' not in request.files:
                error = 'Не выбран файл'
            else:
                file = request.files['fact_file']
                if file.filename == '':
                    error = 'Не выбран файл'
                elif not allowed_file(file.filename):
                    error = 'Недопустимый формат файла'
                else:
                    try:
                        # Сохраняем файл с фактами
                        os.makedirs(date_folder, exist_ok=True)
                        file.save(fact_path)
                        flash('Фактические данные успешно загружены', 'success')
                        return redirect(url_for('project.analysis', date_str=date_str))
                    except Exception as e:
                        error = f'Ошибка сохранения файла: {str(e)}'

        # Если есть оба файла (прогноз и факт)
        if os.path.exists(fact_path) and os.path.exists(predicted_path):
            try:
                actual_df = pd.read_csv(fact_path)
                predicted_df = pd.read_csv(predicted_path)

                # Проверяем, что данные загружены корректно
                if not actual_df.empty and not predicted_df.empty:
                    actual = [{
                        'hour': int(row['hour']),
                        'consumption': float(row['consumption'])
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
                                'prediction': float(pred_row['prediction']),
                                'actual': float(actual_row['consumption']),
                                'difference': float(actual_row['consumption'] - pred_row['prediction']),
                                'percentage_diff': float(((actual_row['consumption'] - pred_row['prediction']) / actual_row[
                                    'consumption']) * 100) if actual_row['consumption'] != 0 else 0
                            }
                            combined_data.append(item)

                    # Вычисляем метрики качества
                    y_true = actual_df['consumption'].astype(float)
                    y_pred = predicted_df['prediction'].astype(float)

                    metrics = {
                        'mae': float(mean_absolute_error(y_true, y_pred)),
                        'rmse': float(mean_squared_error(y_true, y_pred)),
                        'r2': float(r2_score(y_true, y_pred)),
                        'wape': float(calculate_wape(y_true, y_pred))
                    }
            except Exception as e:
                error = f'Ошибка обработки данных: {str(e)}'

    except ValueError:
        flash('Некорректный формат даты', 'error')
        return redirect(url_for('project.analysis_redirect'))
    except Exception as e:
        error = f'Ошибка при анализе данных: {str(e)}'

    return render_template('analysis.html',
                          predicted=predicted,
                          actual=actual,
                          combined_data=combined_data,
                          metrics=metrics,
                          error=error,
                          date_info=date_info)