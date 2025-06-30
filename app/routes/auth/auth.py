from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pytz


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

        # Проверка учетных данных
        if username != ADMIN_USER['username'] or not check_password_hash(ADMIN_USER['password_hash'], password):
            flash('Неверные учетные данные', 'error')
            return redirect(url_for('auth.login'))

        # Успешный вход
        session['logged_in'] = True
        flash('Добро пожаловать!', 'success')
        return redirect(url_for('auth.project'))

    return render_template('auth/login.html')

@auth_bp.route('/project')
def project():
    if not session.get('logged_in'):
        flash('Требуется авторизация', 'error')
        return redirect(url_for('auth.login'))
    utc_now = datetime.utcnow()
    ekaterinburg_tz = pytz.timezone('Asia/Yekaterinburg')  # UTC+5
    now_ekb = utc_now.replace(tzinfo=pytz.utc).astimezone(ekaterinburg_tz)
    return render_template('project.html', now=now_ekb, timedelta=timedelta)

@auth_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('auth.login'))