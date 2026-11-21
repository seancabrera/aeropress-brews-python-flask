import os
import unittest

from api import create_app
from models import Log, Recipe, db


def recipe_body(**overrides):
    body = {
        'beans': 'Onyx Southern Weather',
        'coffee_grams': 15,
        'water_grams': 250,
        'water_temp': 200,
        'grind_setting': 20,
        'brew_time': 150,
        'drink_type': 'hot',
        'instructions': 'Inverted. Stir 10s, steep, flip, press 30s.',
    }
    body.update(overrides)
    return body


class AeropressBrewsTestCase(unittest.TestCase):
    """This class represents the AeroPress Brews API test case"""

    def setUp(self):
        """Define test variables and initialize app."""
        self.database_path = os.environ.get('TEST_DATABASE_URL')
        self.tokens = {
            'contributor': os.environ.get('CONTRIBUTOR_TOKEN'),
            'owner': os.environ.get('OWNER_TOKEN'),
        }
        if not (self.database_path and all(self.tokens.values())):
            raise RuntimeError(
                'TEST_DATABASE_URL, CONTRIBUTOR_TOKEN and OWNER_TOKEN must '
                'be set. Run `source setup.sh` first.')

        self.app = create_app({
            'SQLALCHEMY_DATABASE_URI': self.database_path,
            'TESTING': True
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        """Executed after each test"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    # ---- helpers ---------------------------------------------------------

    def request(self, method, url, role=None, **kwargs):
        """Send a request, authenticated as `role` if one is given."""
        if role:
            kwargs['headers'] = {
                'Authorization': f'Bearer {self.tokens[role]}'}
        res = getattr(self.client, method)(url, **kwargs)
        return res, res.get_json()

    def get(self, url, role=None):
        return self.request('get', url, role)

    def post(self, url, json=None, role=None):
        return self.request('post', url, role, json=json)

    def patch(self, url, json=None, role=None):
        return self.request('patch', url, role, json=json)

    def delete(self, url, role=None):
        return self.request('delete', url, role)

    def create_recipe(self, **fields):
        with self.app.app_context():
            recipe = Recipe(**recipe_body(**fields))
            recipe.insert()
            return recipe.id

    def create_log(self, recipe_id, rating=4, notes='Sweet, a little thin'):
        with self.app.app_context():
            log = Log(recipe_id=recipe_id, rating=rating, notes=notes)
            log.insert()
            return log.id

    # ---- GET / -----------------------------------------------------------

    def test_index(self):
        res, data = self.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data['success'])

    # ---- GET /recipes ----------------------------------------------------

    def test_get_recipes_public(self):
        self.create_recipe()
        self.create_recipe(drink_type='iced')

        res, data = self.get('/recipes')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['total_recipes'], 2)
        self.assertEqual(len(data['recipes']), 2)

    def test_get_recipes_filtered_by_drink_type(self):
        self.create_recipe()
        self.create_recipe(drink_type='iced')

        res, data = self.get('/recipes?drink_type=iced')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(data['total_recipes'], 1)
        self.assertEqual(data['recipes'][0]['drink_type'], 'iced')

    def test_get_recipes_invalid_drink_type(self):
        res, data = self.get('/recipes?drink_type=latte')

        self.assertEqual(res.status_code, 422)
        self.assertFalse(data['success'])

    # ---- GET /recipes/<id> -----------------------------------------------

    def test_get_recipe_success(self):
        parent_id = self.create_recipe()
        child_id = self.create_recipe(based_on_id=parent_id, grind_setting=18)
        self.create_log(parent_id)

        res, data = self.get(f'/recipes/{parent_id}')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(data['recipe']['id'], parent_id)
        self.assertEqual(data['recipe']['derived_recipe_ids'], [child_id])
        self.assertEqual(data['recipe']['log_count'], 1)

    def test_get_recipe_not_found(self):
        res, data = self.get('/recipes/9999')

        self.assertEqual(res.status_code, 404)
        self.assertFalse(data['success'])

    # ---- GET /recipes/<id>/logs ------------------------------------------

    def test_get_recipe_logs_success(self):
        recipe_id = self.create_recipe()
        self.create_log(recipe_id, rating=3)
        self.create_log(recipe_id, rating=5)

        res, data = self.get(f'/recipes/{recipe_id}/logs')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(data['total_logs'], 2)

    def test_get_recipe_logs_not_found(self):
        res, data = self.get('/recipes/9999/logs')

        self.assertEqual(res.status_code, 404)
        self.assertFalse(data['success'])

    # ---- POST /recipes ---------------------------------------------------

    def test_create_recipe_as_contributor(self):
        res, data = self.post('/recipes', recipe_body(), role='contributor')

        self.assertEqual(res.status_code, 201)
        self.assertTrue(data['success'])
        self.assertEqual(data['recipe']['water_temp'], 200)
        with self.app.app_context():
            self.assertEqual(Recipe.query.count(), 1)

    def test_create_recipe_as_owner(self):
        res, data = self.post('/recipes', recipe_body(), role='owner')
        self.assertEqual(res.status_code, 201)

    def test_create_recipe_based_on_another(self):
        parent_id = self.create_recipe()
        body = recipe_body(
            grind_setting=18,
            based_on_id=parent_id,
            adjustments='Two clicks finer; last one tasted sour.')

        res, data = self.post('/recipes', body, role='contributor')

        self.assertEqual(res.status_code, 201)
        self.assertEqual(data['recipe']['based_on_id'], parent_id)

    def test_create_recipe_without_token(self):
        res, data = self.post('/recipes', recipe_body())

        self.assertEqual(res.status_code, 401)
        self.assertFalse(data['success'])

    def test_create_recipe_missing_field(self):
        body = recipe_body()
        del body['beans']

        res, data = self.post('/recipes', body, role='contributor')

        self.assertEqual(res.status_code, 422)
        self.assertIn('beans', data['message'])

    def test_create_recipe_grind_out_of_range(self):
        body = recipe_body(grind_setting=41)
        res, data = self.post('/recipes', body, role='contributor')
        self.assertEqual(res.status_code, 422)

    def test_create_recipe_fractional_grams(self):
        body = recipe_body(coffee_grams=17.5)
        res, data = self.post('/recipes', body, role='contributor')
        self.assertEqual(res.status_code, 422)

    def test_create_recipe_bad_based_on(self):
        body = recipe_body(based_on_id=9999)
        res, data = self.post('/recipes', body, role='contributor')
        self.assertEqual(res.status_code, 422)

    def test_create_recipe_no_body(self):
        res, data = self.post('/recipes', role='contributor')

        self.assertEqual(res.status_code, 400)
        self.assertFalse(data['success'])

    # ---- PATCH /recipes/<id> ---------------------------------------------

    def test_update_recipe_as_contributor(self):
        recipe_id = self.create_recipe()

        res, data = self.patch(f'/recipes/{recipe_id}', {'water_temp': 185},
                               role='contributor')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(data['recipe']['water_temp'], 185)
        self.assertEqual(data['recipe']['beans'], 'Onyx Southern Weather')

    def test_update_recipe_without_token(self):
        recipe_id = self.create_recipe()
        res, data = self.patch(f'/recipes/{recipe_id}', {'water_temp': 185})
        self.assertEqual(res.status_code, 401)

    def test_update_recipe_not_found(self):
        res, data = self.patch('/recipes/9999', {'water_temp': 185},
                               role='contributor')
        self.assertEqual(res.status_code, 404)

    def test_update_recipe_invalid_temp(self):
        recipe_id = self.create_recipe()
        res, data = self.patch(f'/recipes/{recipe_id}', {'water_temp': 250},
                               role='contributor')
        self.assertEqual(res.status_code, 422)

    def test_update_recipe_cycle_rejected(self):
        parent_id = self.create_recipe()
        child_id = self.create_recipe(based_on_id=parent_id)
        res, data = self.patch(f'/recipes/{parent_id}',
                               {'based_on_id': child_id}, role='contributor')
        self.assertEqual(res.status_code, 422)

    # ---- DELETE /recipes/<id> --------------------------------------------

    def test_delete_recipe_as_owner_cascades_logs(self):
        parent_id = self.create_recipe()
        child_id = self.create_recipe(based_on_id=parent_id)
        self.create_log(parent_id)
        self.create_log(parent_id)

        res, data = self.delete(f'/recipes/{parent_id}', role='owner')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(data['deleted'], parent_id)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Recipe, parent_id))
            self.assertEqual(Log.query.count(), 0)
            child = db.session.get(Recipe, child_id)
            self.assertIsNone(child.based_on_id)

    def test_delete_recipe_as_contributor_forbidden(self):
        recipe_id = self.create_recipe()

        res, data = self.delete(f'/recipes/{recipe_id}', role='contributor')

        self.assertEqual(res.status_code, 403)
        self.assertFalse(data['success'])
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Recipe, recipe_id))

    def test_delete_recipe_without_token(self):
        recipe_id = self.create_recipe()
        res, data = self.delete(f'/recipes/{recipe_id}')
        self.assertEqual(res.status_code, 401)

    def test_delete_recipe_not_found(self):
        res, data = self.delete('/recipes/9999', role='owner')
        self.assertEqual(res.status_code, 404)

    # ---- POST /recipes/<id>/logs -----------------------------------------

    def test_create_log_as_contributor(self):
        recipe_id = self.create_recipe()
        body = {'rating': 5, 'notes': 'Juicy, clean finish'}

        res, data = self.post(f'/recipes/{recipe_id}/logs', body,
                              role='contributor')

        self.assertEqual(res.status_code, 201)
        self.assertEqual(data['log']['recipe_id'], recipe_id)
        self.assertIsNotNone(data['log']['brewed_at'])

    def test_create_log_with_brewed_at(self):
        recipe_id = self.create_recipe()
        body = {'rating': 3, 'brewed_at': '2026-11-01T08:30:00'}

        res, data = self.post(f'/recipes/{recipe_id}/logs', body,
                              role='owner')

        self.assertEqual(res.status_code, 201)
        self.assertTrue(
            data['log']['brewed_at'].startswith('2026-11-01T08:30:00'))

    def test_create_log_without_token(self):
        recipe_id = self.create_recipe()
        res, data = self.post(f'/recipes/{recipe_id}/logs', {'rating': 5})
        self.assertEqual(res.status_code, 401)

    def test_create_log_invalid_rating(self):
        recipe_id = self.create_recipe()
        res, data = self.post(f'/recipes/{recipe_id}/logs', {'rating': 6},
                              role='contributor')
        self.assertEqual(res.status_code, 422)

    def test_create_log_recipe_not_found(self):
        res, data = self.post('/recipes/9999/logs', {'rating': 5},
                              role='contributor')
        self.assertEqual(res.status_code, 404)

    # ---- PATCH /logs/<id> ------------------------------------------------

    def test_update_log_as_contributor(self):
        log_id = self.create_log(self.create_recipe())

        res, data = self.patch(f'/logs/{log_id}',
                               {'rating': 2, 'notes': 'Bitter'},
                               role='contributor')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(data['log']['rating'], 2)
        self.assertEqual(data['log']['notes'], 'Bitter')

    def test_update_log_without_token(self):
        log_id = self.create_log(self.create_recipe())
        res, data = self.patch(f'/logs/{log_id}', {'rating': 2})
        self.assertEqual(res.status_code, 401)

    def test_update_log_not_found(self):
        res, data = self.patch('/logs/9999', {'rating': 2},
                               role='contributor')
        self.assertEqual(res.status_code, 404)

    def test_update_log_unknown_field(self):
        log_id = self.create_log(self.create_recipe())
        res, data = self.patch(f'/logs/{log_id}', {'recipe_id': 2},
                               role='contributor')
        self.assertEqual(res.status_code, 422)

    # ---- DELETE /logs/<id> -----------------------------------------------

    def test_delete_log_as_owner(self):
        log_id = self.create_log(self.create_recipe())

        res, data = self.delete(f'/logs/{log_id}', role='owner')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(data['deleted'], log_id)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Log, log_id))

    def test_delete_log_as_contributor_forbidden(self):
        log_id = self.create_log(self.create_recipe())
        res, data = self.delete(f'/logs/{log_id}', role='contributor')
        self.assertEqual(res.status_code, 403)

    def test_delete_log_not_found(self):
        res, data = self.delete('/logs/9999', role='owner')
        self.assertEqual(res.status_code, 404)


# Make the tests conveniently executable
if __name__ == "__main__":
    unittest.main()
