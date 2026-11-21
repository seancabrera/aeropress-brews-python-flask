from flask import Flask, jsonify
from flask_cors import CORS

from auth.auth import AuthError
from models import setup_db
from .logs_controller import logs_bp
from .recipes_controller import recipes_bp


def create_app(test_config=None):
    """Create and configure the AeroPress Brews API."""
    app = Flask(__name__)

    if test_config is None:
        setup_db(app)
    else:
        # Apply everything (e.g. TESTING), then let setup_db normalize the
        # database URL.
        app.config.update(test_config)
        setup_db(app, database_path=test_config['SQLALCHEMY_DATABASE_URI'])

    # Flask-CORS sends the CORS headers, including preflight responses.
    CORS(
        app,
        origins='*',
        allow_headers=['Content-Type', 'Authorization'],
        methods=['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
    )

    @app.route('/')
    def index():
        return jsonify({
            'success': True,
            'message': 'AeroPress Brews API. See the README for endpoints.'
        })

    app.register_blueprint(recipes_bp)
    app.register_blueprint(logs_bp)

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(422)
    @app.errorhandler(500)
    def handle_error(error):
        return jsonify({
            'success': False,
            'error': error.code,
            'message': error.description
        }), error.code

    @app.errorhandler(AuthError)
    def handle_auth_error(error):
        return jsonify({
            'success': False,
            'error': error.status_code,
            'message': error.error['description']
        }), error.status_code

    return app
