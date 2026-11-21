from flask import Blueprint, abort, jsonify, request

from auth.auth import requires_auth
from models import DRINK_TYPES, Recipe, db
from .helpers import commit_or_422, get_or_404
from .validation import RECIPE_FIELDS, get_request_body, validate_body

recipes_bp = Blueprint('recipes', __name__)


def check_based_on(recipe_id, based_on_id):
    """Ensure the parent recipe exists and the link wouldn't form a loop."""
    if based_on_id is None:
        return
    parent = db.session.get(Recipe, based_on_id)
    if parent is None:
        abort(422, description=f'based_on_id {based_on_id} does not exist')

    # Walk up the ancestry; reaching this recipe means a cycle.
    node = parent
    while node is not None:
        if node.id == recipe_id:
            abort(422, description=(
                'A recipe cannot be based on itself or one of its '
                'descendants'))
        node = node.based_on


@recipes_bp.route('/recipes', methods=['GET'])
def get_recipes():
    """Public. List recipes, optionally filtered with ?drink_type=."""
    query = Recipe.query.order_by(Recipe.id)

    drink_type = request.args.get('drink_type')
    if drink_type is not None:
        if drink_type not in DRINK_TYPES:
            abort(422, description=(
                f"drink_type must be one of: {', '.join(DRINK_TYPES)}"))
        query = query.filter(Recipe.drink_type == drink_type)

    recipes = query.all()
    return jsonify({
        'success': True,
        'recipes': [recipe.format() for recipe in recipes],
        'total_recipes': len(recipes)
    })


@recipes_bp.route('/recipes/<int:recipe_id>', methods=['GET'])
def get_recipe(recipe_id):
    """Public. One recipe, plus derived recipe ids and its log count."""
    recipe = get_or_404(Recipe, recipe_id)
    data = recipe.format()
    data['derived_recipe_ids'] = sorted(r.id for r in recipe.derived_recipes)
    data['log_count'] = len(recipe.logs)
    return jsonify({
        'success': True,
        'recipe': data
    })


@recipes_bp.route('/recipes', methods=['POST'])
@requires_auth('post:recipes')
def create_recipe(payload):
    """Requires 'post:recipes'. Create a recipe."""
    data = validate_body(get_request_body(), RECIPE_FIELDS)
    check_based_on(None, data.get('based_on_id'))

    recipe = Recipe(**data)
    commit_or_422(recipe.insert)
    return jsonify({
        'success': True,
        'recipe': recipe.format()
    }), 201


@recipes_bp.route('/recipes/<int:recipe_id>', methods=['PATCH'])
@requires_auth('patch:recipes')
def update_recipe(payload, recipe_id):
    """Requires 'patch:recipes'. Update only the fields sent."""
    recipe = get_or_404(Recipe, recipe_id)
    data = validate_body(get_request_body(), RECIPE_FIELDS, partial=True)
    if 'based_on_id' in data:
        check_based_on(recipe.id, data['based_on_id'])

    for field, value in data.items():
        setattr(recipe, field, value)
    commit_or_422(recipe.update)
    return jsonify({
        'success': True,
        'recipe': recipe.format()
    })


@recipes_bp.route('/recipes/<int:recipe_id>', methods=['DELETE'])
@requires_auth('delete:recipes')
def delete_recipe(payload, recipe_id):
    """Requires 'delete:recipes'.

    Deletes the recipe's logs too. Recipes based on it are kept, with
    based_on_id cleared.
    """
    recipe = get_or_404(Recipe, recipe_id)
    commit_or_422(recipe.delete)
    return jsonify({
        'success': True,
        'deleted': recipe_id
    })
