from flask import Blueprint, jsonify

from auth.auth import requires_auth
from models import Log, Recipe
from .helpers import commit_or_422, get_or_404
from .validation import LOG_FIELDS, get_request_body, validate_body

logs_bp = Blueprint('logs', __name__)


@logs_bp.route('/recipes/<int:recipe_id>/logs', methods=['GET'])
def get_recipe_logs(recipe_id):
    """Public. A recipe's logs, newest first."""
    recipe = get_or_404(Recipe, recipe_id)
    return jsonify({
        'success': True,
        'recipe_id': recipe.id,
        'logs': [log.format() for log in recipe.logs],
        'total_logs': len(recipe.logs)
    })


@logs_bp.route('/recipes/<int:recipe_id>/logs', methods=['POST'])
@requires_auth('post:logs')
def create_log(payload, recipe_id):
    """Requires 'post:logs'. brewed_at defaults to now when omitted."""
    recipe = get_or_404(Recipe, recipe_id)
    data = validate_body(get_request_body(), LOG_FIELDS,
                         optional_on_create=('brewed_at',))

    log = Log(recipe_id=recipe.id, **data)
    commit_or_422(log.insert)
    return jsonify({
        'success': True,
        'log': log.format()
    }), 201


@logs_bp.route('/logs/<int:log_id>', methods=['PATCH'])
@requires_auth('patch:logs')
def update_log(payload, log_id):
    """Requires 'patch:logs'. Update only the fields sent."""
    log = get_or_404(Log, log_id)
    data = validate_body(get_request_body(), LOG_FIELDS, partial=True)

    for field, value in data.items():
        setattr(log, field, value)
    commit_or_422(log.update)
    return jsonify({
        'success': True,
        'log': log.format()
    })


@logs_bp.route('/logs/<int:log_id>', methods=['DELETE'])
@requires_auth('delete:logs')
def delete_log(payload, log_id):
    """Requires 'delete:logs'."""
    log = get_or_404(Log, log_id)
    commit_or_422(log.delete)
    return jsonify({
        'success': True,
        'deleted': log_id
    })
