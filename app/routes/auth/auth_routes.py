from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from werkzeug.security import check_password_hash
from .constants import ADMIN_USER
from .date_utils import get_tomorrow_date  # Добавляем импорт

auth_bp = Blueprint('auth', __name__)

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
        # Перенаправляем на страницу проекта с завтрашней датой
        tomorrow_date = get_tomorrow_date().strftime('%d-%m-%Y')
        return redirect(url_for('project.project', date_str=tomorrow_date))

    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('auth.login'))