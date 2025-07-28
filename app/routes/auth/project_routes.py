from flask import render_template, redirect, session, flash, request, url_for, Blueprint, jsonify
from werkzeug.utils import secure_filename
from .file_utils import allowed_file, process_weather_file
from .date_utils import get_date_info, parse_date, get_tomorrow_date
from .constants import LOCATIONS
import os
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from datetime import datetime, timedelta
from .model_utils import prepare_features, MODEL, calculate_wape
import numpy as np

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
    previous_day_data = None

    # Получаем данные за предыдущие сутки
    prev_date = target_date - timedelta(days=1)
    prev_date_str = prev_date.strftime('%d.%m.%Y')
    prev_date_folder = os.path.join(UPLOAD_FOLDER, prev_date_str)
    prev_fact_path = os.path.join(prev_date_folder, 'fact.csv')

    if os.path.exists(prev_fact_path):
        try:
            with open(prev_fact_path, 'r', encoding='utf-8-sig') as f:
                prev_df = pd.read_csv(f)
                previous_day_data = {
                    int(row['hour']): float(row['consumption'])
                    for _, row in prev_df.iterrows()
                }
                print(f"Данные предыдущего дня: {previous_day_data}")
        except Exception as e:
            print(f"Ошибка загрузки данных предыдущего дня: {str(e)}")
            flash(f'Ошибка загрузки данных предыдущего дня: {str(e)}', 'error')

    # Проверяем наличие сохранённых данных
    date_folder = os.path.join(UPLOAD_FOLDER, target_date.strftime('%d.%m.%Y'))
    csv_path = os.path.join(date_folder, 'features_table.csv')

    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            weather_data = []
            for _, row in df.iterrows():
                hour = int(row['Час'])
                display_hour = hour - 1 if hour > 0 else 23

                # Получаем потребление за тот же час предыдущего дня
                lag_24 = previous_day_data.get(hour, 0) if previous_day_data else 0

                for loc in LOCATIONS:
                    loc_name = loc['name']
                    weather_data.append({
                        'Локация': loc_name,
                        'Час': f"{display_hour:02d}:00",
                        'Температура (°C)': row[f"{loc_name}_temp"],
                        'Влажность (%)': row[f"{loc_name}_humidity"],
                        'Давление (гПа)': row[f"{loc_name}_pressure"],
                        'Скорость ветра (м/с)': row[f"{loc_name}_wind"],
                        'lag_24': lag_24
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

                    for hour in range(24):
                        display_hour = hour
                        save_hour = hour + 1 if hour < 23 else 0

                        # Получаем потребление за тот же час предыдущего дня
                        lag_24 = previous_day_data.get(hour, 0) if previous_day_data else 0

                        hour_data = {
                            'Час': save_hour,
                            'День_недели': date_info['day_of_week'],
                            'Неделя_года': date_info['week_of_year'],
                            'Рабочий_день': date_info['is_workday'],
                            'lag_24': lag_24
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

                    # --- КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: Упорядочиваем столбцы перед сохранением ---
                    if hasattr(MODEL, 'feature_names_in_'):
                        # Для sklearn-стиля модели
                        correct_order = MODEL.feature_names_in_
                    else:
                        # Для нативного XGBoost
                        correct_order = MODEL.get_booster().feature_names

                    # Проверяем, что все нужные колонки есть
                    missing_cols = set(correct_order) - set(df.columns)
                    if missing_cols:
                        raise ValueError(f"Отсутствуют колонки: {missing_cols}")

                    # Упорядочиваем и сохраняем
                    df = df[correct_order]
                    df.to_csv(csv_path, index=False, encoding='utf-8')

                    flash('Файл успешно загружен и данные сохранены', 'success')
                    return redirect(url_for('project.project', date_str=date_str))
            except Exception as e:
                flash(f'Ошибка обработки файла: {str(e)}', 'error')

    return render_template('project.html',
                           weather_data=weather_data,
                           locations=LOCATIONS,
                           date_info=date_info,
                           previous_day_data=previous_day_data)


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
        # 1. Парсинг даты и подготовка путей
        target_date = parse_date(date_str, '%d-%m-%Y')
        date_folder = os.path.join(UPLOAD_FOLDER, target_date.strftime('%d.%m.%Y'))
        features_path = os.path.join(date_folder, 'features_table.csv')
        predictions_path = os.path.join(date_folder, 'predicted.csv')

        # 2. Проверка наличия файла с признаками
        if not os.path.exists(features_path):
            flash('Сначала загрузите данные о погоде', 'error')
            return redirect(url_for('project.project', date_str=date_str))

        # 3. Загрузка и проверка данных
        features = pd.read_csv(features_path)

        if len(features) != 24:
            flash('Должно быть 24 записи (по одной на каждый час)', 'error')
            return redirect(url_for('project.project', date_str=date_str))

        # 4. Упорядочивание признаков
        if hasattr(MODEL, 'feature_names_in_'):
            features = features[MODEL.feature_names_in_]
        else:
            features = features[MODEL.get_booster().feature_names]

        # 5. Получение и обработка предсказаний
        raw_predictions = MODEL.predict(features)

        # Округление до 2 знаков
        rounded_predictions = [round(float(pred), 2) for pred in raw_predictions]

        # Сдвиг на 1 вправо (ротация массива)
        shifted_predictions = np.roll(rounded_predictions, 1)

        # Замена первого элемента на последний из исходного
        shifted_predictions[0] = rounded_predictions[-1]

        # 6. Сохранение результатов
        results = [{'hour': hour, 'prediction': pred}
                   for hour, pred in enumerate(shifted_predictions)]

        pd.DataFrame(results).to_csv(predictions_path, index=False)

        # 7. Подготовка данных для отображения
        return render_template('predict.html',
                               predictions=results,
                               date_info=get_date_info(target_date))

    except ValueError:
        flash('Некорректный формат даты', 'error')
        return redirect(url_for('project.predict_redirect'))
    except Exception as e:
        flash(f'Ошибка при прогнозировании: {str(e)}', 'error')
        return redirect(url_for('project.project', date_str=date_str))


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
    previous_day_data = None
    combined_data = []
    metrics = None
    prev_day_metrics = None
    date_info = None

    try:
        # Парсим дату из URL
        target_date = parse_date(date_str, '%d-%m-%Y')
        date_info = get_date_info(target_date)

        # Получаем дату предыдущего дня
        prev_date = target_date - timedelta(days=1)
        prev_date_str = prev_date.strftime('%d.%m.%Y')
        prev_date_folder = os.path.join(UPLOAD_FOLDER, prev_date_str)
        prev_date_fact_path = os.path.join(prev_date_folder, 'fact.csv')

        # Пути к файлам текущего дня
        date_folder = os.path.join(UPLOAD_FOLDER, target_date.strftime('%d.%m.%Y'))
        predicted_path = os.path.join(date_folder, 'predicted.csv')
        fact_path = os.path.join(date_folder, 'fact.csv')

        print(f"\n=== Отладочная информация ===")
        print(f"Текущая дата: {target_date.strftime('%d.%m.%Y')}")
        print(f"Путь к predicted.csv: {predicted_path} (существует: {os.path.exists(predicted_path)})")
        print(f"Путь к fact.csv: {fact_path} (существует: {os.path.exists(fact_path)})")
        print(f"Дата предыдущего дня: {prev_date_str}")
        print(
            f"Путь к fact.csv предыдущего дня: {prev_date_fact_path} (существует: {os.path.exists(prev_date_fact_path)})\n")

        # Загружаем прогнозируемые данные если они есть
        if os.path.exists(predicted_path):
            predicted_df = pd.read_csv(predicted_path)
            predicted = [{
                'hour': int(row['hour']),
                'prediction': float(row['prediction'])
            } for _, row in predicted_df.iterrows()]
            print(f"Загружено {len(predicted)} прогнозируемых значений")

        # Загружаем фактические данные текущего дня если они есть
        if os.path.exists(fact_path):
            actual_df = pd.read_csv(fact_path)
            actual = [{
                'hour': int(row['hour']),
                'consumption': float(row['consumption'])
            } for _, row in actual_df.iterrows()]
            print(f"Загружено {len(actual)} фактических значений")

        # Загружаем данные предыдущего дня если они есть
        if os.path.exists(prev_date_fact_path):
            prev_day_df = pd.read_csv(prev_date_fact_path)
            previous_day_data = [{
                'hour': int(row['hour']),
                'consumption': float(row['consumption'])
            } for _, row in prev_day_df.iterrows()]
            print(f"Загружено {len(previous_day_data)} значений предыдущего дня")

            # Вычисляем метрики для предыдущего дня если есть фактические данные текущего дня
            if actual and predicted:
                y_true = [item['consumption'] for item in actual]
                y_pred_prev_day = []

                # Сопоставляем часы предыдущего дня с текущим днём
                for item in actual:
                    prev_item = next((x for x in previous_day_data if x['hour'] == item['hour']), None)
                    y_pred_prev_day.append(prev_item['consumption'] if prev_item else 0)

                if len(y_true) == len(y_pred_prev_day):
                    prev_day_metrics = {
                        'mae': float(mean_absolute_error(y_true, y_pred_prev_day)),
                        'rmse': float(mean_squared_error(y_true, y_pred_prev_day)),
                        'r2': float(r2_score(y_true, y_pred_prev_day)),
                        'wape': float(calculate_wape(y_true, y_pred_prev_day))
                    }
                    print("Метрики предыдущего дня рассчитаны:", prev_day_metrics)

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
        if actual and predicted:
            try:
                # Подготавливаем объединенные данные для таблицы
                for hour in range(24):
                    # Получаем данные прогноза
                    pred_item = next((x for x in predicted if x['hour'] == hour), None)

                    # Получаем фактические данные
                    actual_item = next((x for x in actual if x['hour'] == hour), None)

                    if pred_item and actual_item:
                        item = {
                            'hour': hour,
                            'prediction': pred_item['prediction'],
                            'actual': actual_item['consumption'],
                            'difference': actual_item['consumption'] - pred_item['prediction'],
                            'percentage_diff': ((actual_item['consumption'] - pred_item['prediction']) / actual_item[
                                'consumption']) * 100 if actual_item['consumption'] != 0 else 0
                        }

                        # Добавляем данные предыдущего дня если они есть
                        if previous_day_data:
                            prev_item = next((x for x in previous_day_data if x['hour'] == hour), None)
                            if prev_item:
                                item.update({
                                    'prev_day': prev_item['consumption'],
                                    'prev_day_diff': actual_item['consumption'] - prev_item['consumption'],
                                    'prev_day_percentage_diff': ((actual_item['consumption'] - prev_item[
                                        'consumption']) / actual_item['consumption']) * 100 if actual_item[
                                                                                                   'consumption'] != 0 else 0
                                })

                        combined_data.append(item)

                # Вычисляем метрики качества
                y_true = [x['consumption'] for x in actual]
                y_pred = [x['prediction'] for x in predicted]

                metrics = {
                    'mae': float(mean_absolute_error(y_true, y_pred)),
                    'rmse': float(mean_squared_error(y_true, y_pred)),
                    'r2': float(r2_score(y_true, y_pred)),
                    'wape': float(calculate_wape(y_true, y_pred))
                }
                print("Метрики текущего дня рассчитаны:", metrics)

            except Exception as e:
                error = f'Ошибка обработки данных: {str(e)}'
                print(f"Ошибка при обработке данных: {str(e)}")

    except ValueError:
        flash('Некорректный формат даты', 'error')
        return redirect(url_for('project.analysis_redirect'))
    except Exception as e:
        error = f'Ошибка при анализе данных: {str(e)}'
        print(f"Критическая ошибка: {str(e)}")

    return render_template('analysis.html',
                           predicted=predicted,
                           actual=actual,
                           previous_day_data=previous_day_data,
                           combined_data=combined_data,
                           metrics=metrics,
                           prev_day_metrics=prev_day_metrics,
                           error=error,
                           date_info=date_info)