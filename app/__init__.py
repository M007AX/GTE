from flask import Flask


def create_app():
    app = Flask(__name__, static_folder='../static')
    app.secret_key = 'secret_key_123'  # Нужно для работы сессий

    # Регистрируем маршруты
    from .routes.auth.auth_routes import auth_bp
    from .routes.auth.project_routes import project
    from .routes.auth.model_utils import prepare_features, MODEL
    from .routes.auth.constants import ADMIN_USER, LOCATIONS
    from .routes.auth.file_utils import allowed_file, process_weather_file

    app.register_blueprint(auth_bp)

    return app