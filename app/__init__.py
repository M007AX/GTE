from flask import Flask


def create_app():
    app = Flask(__name__, static_folder='../static')
    app.secret_key = 'secret_key_123'  # Нужно для работы сессий

    # Регистрируем маршруты
    from app.routes.auth.auth import auth_bp
    app.register_blueprint(auth_bp)

    return app