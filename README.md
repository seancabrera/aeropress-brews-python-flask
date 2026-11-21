# AeroPress Brews

A REST API for dialing in AeroPress recipes. Each **recipe** is a fixed set of brew parameters; each time you brew it you add a **log** with a rating and tasting notes. Tweaking a parameter means creating a new recipe, optionally linked to the one it was based on, so you can trace how a recipe evolved.

Capstone project for the Udacity Full Stack Web Developer Nanodegree.

**Live API:** `https://YOUR-APP.onrender.com` _(update after deploying)_

Reading is public by design, so anyone can browse recipes and logs with no account. Creating, editing and deleting require an Auth0 account with the right role.

## Motivation

Dialing in an AeroPress recipe means changing one variable at a time (grind, temperature, steep time) and remembering how each version tasted. Notes apps and spreadsheets make it hard to see which change helped. This API treats every variation as its own recipe, linked to the one it came from, and keeps a log of each brew, so the history of how a recipe got better stays intact. It's the backend for a planned mobile app.

## Tech stack

- Python 3.12, Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-CORS
- PostgreSQL
- Auth0 (JWT, role-based access control)
- Hosted on Render

## Project structure

```
├── api/
│   ├── __init__.py            # create_app(), error handlers
│   ├── recipes_controller.py  # /recipes endpoints
│   ├── logs_controller.py     # /recipes/<id>/logs and /logs endpoints
│   ├── helpers.py             # shared 404 lookup and commit handling
│   └── validation.py          # request body validation
├── auth/auth.py               # Auth0 JWT verification, @requires_auth
├── models.py                  # Recipe and Log models, setup_db()
├── migrations/                # Flask-Migrate (Alembic) migrations
├── test_app.py                # unittest suite
├── setup.sh                   # environment variables
└── render.yaml                # Render deployment blueprint
```

## Data model

**Recipe**

| Field | Type | Notes |
|---|---|---|
| `id` | integer | |
| `beans` | string | required, max 200 chars |
| `coffee_grams` | integer | required, > 0 |
| `water_grams` | integer | required, > 0 |
| `water_temp` | integer | required, °F, 32–212 |
| `grind_setting` | integer | required, Baratza Encore ESP setting, 1–40 |
| `brew_time` | integer | required, seconds, > 0 |
| `drink_type` | string | required, `hot`, `iced` or `espresso` |
| `instructions` | string | optional |
| `based_on_id` | integer | optional, id of the recipe this one was tweaked from |
| `adjustments` | string | optional, what changed from the parent recipe and why |

**Log** (many logs per recipe)

| Field | Type | Notes |
|---|---|---|
| `id` | integer | |
| `recipe_id` | integer | the recipe that was brewed |
| `brewed_at` | ISO 8601 date-time | defaults to now |
| `rating` | integer | required, 1–5 |
| `notes` | string | optional |

Deleting a recipe deletes its logs. Recipes based on a deleted recipe are kept, with `based_on_id` set to `null`.

## Local setup

1. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create the databases:

   ```bash
   createdb aeropress
   createdb aeropress_test
   ```

3. Edit `setup.sh` with your database URLs, Auth0 settings and role tokens, then load it. It exports:

   | Variable | Purpose |
   |---|---|
   | `DATABASE_URL`, `TEST_DATABASE_URL` | Postgres connections for the app and the tests |
   | `AUTH0_DOMAIN` | Auth0 tenant domain |
   | `AUTH0_CLIENT_ID` | Auth0 application used to log in and get tokens |
   | `API_AUDIENCE` | Auth0 API identifier |
   | `ALGORITHMS` | `RS256`. Tokens are signed with Auth0's private key and verified with its public keys (JWKS), so there is no shared signing secret to configure |
   | `CONTRIBUTOR_TOKEN`, `OWNER_TOKEN` | JWTs for each role, used by the tests and by reviewers |


   ```bash
   source setup.sh
   ```

4. Run migrations and start the server:

   ```bash
   flask db upgrade
   flask run --debug
   ```

## Authentication and roles

Auth0 setup:

1. Create an API with identifier (audience) `aeropress-brews` and signing algorithm RS256.
2. In the API settings, enable **RBAC** and **Add Permissions in the Access Token**.
3. Add the permissions below, create the two roles, and assign them to users.

| Permission | Contributor | Owner |
|---|:-:|:-:|
| `post:recipes` | ✅ | ✅ |
| `patch:recipes` | ✅ | ✅ |
| `post:logs` | ✅ | ✅ |
| `patch:logs` | ✅ | ✅ |
| `delete:recipes` | | ✅ |
| `delete:logs` | | ✅ |

GET endpoints need no token. Protected endpoints expect an `Authorization: Bearer <token>` header and return **401** if the token is missing or invalid, or **403** if it lacks the permission.

To get a token, log in through Auth0's authorize URL and copy `access_token` from the redirect:

```
https://YOUR_TENANT.us.auth0.com/authorize?audience=aeropress-brews&response_type=token&client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:5000/
```

## Running tests

Tests use the `TEST_DATABASE_URL` database (tables are created and dropped for each test) and the `CONTRIBUTOR_TOKEN` and `OWNER_TOKEN` from `setup.sh`.

```bash
source setup.sh
python -m unittest test_app -v
```

## API reference

All responses are JSON with a `success` flag.

### Errors

```json
{ "success": false, "error": 404, "message": "Recipe 42 not found" }
```

| Code | Meaning |
|---|---|
| 400 | Body missing, not JSON, or a PATCH with no fields |
| 401 | Missing or invalid token |
| 403 | Token lacks the required permission |
| 404 | Recipe or log not found |
| 405 | Method not allowed |
| 422 | Validation failed (message explains which field) |
| 500 | Server error |

### GET /recipes

Public. Optional query parameter `drink_type` (`hot`, `iced`, `espresso`).

```bash
curl https://YOUR-APP.onrender.com/recipes?drink_type=hot
```

```json
{
  "success": true,
  "total_recipes": 1,
  "recipes": [
    {
      "id": 1,
      "beans": "Onyx Southern Weather",
      "coffee_grams": 15,
      "water_grams": 250,
      "water_temp": 200,
      "grind_setting": 20,
      "brew_time": 150,
      "drink_type": "hot",
      "instructions": "Inverted. Stir 10s, steep, flip, press 30s.",
      "based_on_id": null,
      "adjustments": null
    }
  ]
}
```

### GET /recipes/&lt;id&gt;

Public. Returns one recipe plus `derived_recipe_ids` (recipes based on it) and `log_count`.

```json
{
  "success": true,
  "recipe": { "id": 1, "beans": "Onyx Southern Weather", "...": "...", "derived_recipe_ids": [2], "log_count": 3 }
}
```

### GET /recipes/&lt;id&gt;/logs

Public. Logs for a recipe, newest first.

```json
{
  "success": true,
  "recipe_id": 1,
  "total_logs": 1,
  "logs": [
    { "id": 1, "recipe_id": 1, "brewed_at": "2026-11-19T08:30:00+00:00", "rating": 4, "notes": "Sweet, a little thin" }
  ]
}
```

### POST /recipes

Requires `post:recipes`. All required fields must be sent. Returns **201**.

```bash
curl -X POST https://YOUR-APP.onrender.com/recipes \
  -H "Authorization: Bearer $CONTRIBUTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"beans": "Onyx Southern Weather", "coffee_grams": 15, "water_grams": 250,
       "water_temp": 200, "grind_setting": 18, "brew_time": 150, "drink_type": "hot",
       "based_on_id": 1, "adjustments": "Two clicks finer; last one tasted sour."}'
```

```json
{ "success": true, "recipe": { "id": 2, "...": "..." } }
```

### PATCH /recipes/&lt;id&gt;

Requires `patch:recipes`. Send only the fields to change.

```bash
curl -X PATCH https://YOUR-APP.onrender.com/recipes/2 \
  -H "Authorization: Bearer $CONTRIBUTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"instructions": "Inverted. Stir 15s."}'
```

```json
{ "success": true, "recipe": { "id": 2, "instructions": "Inverted. Stir 15s.", "...": "..." } }
```

### DELETE /recipes/&lt;id&gt;

Requires `delete:recipes`. Also deletes the recipe's logs.

```json
{ "success": true, "deleted": 2 }
```

### POST /recipes/&lt;id&gt;/logs

Requires `post:logs`. `rating` is required; `notes` and `brewed_at` are optional. Returns **201**.

```bash
curl -X POST https://YOUR-APP.onrender.com/recipes/1/logs \
  -H "Authorization: Bearer $CONTRIBUTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rating": 5, "notes": "Juicy, clean finish"}'
```

```json
{ "success": true, "log": { "id": 7, "recipe_id": 1, "brewed_at": "2026-11-19T08:30:00+00:00", "rating": 5, "notes": "Juicy, clean finish" } }
```

### PATCH /logs/&lt;id&gt;

Requires `patch:logs`. Send only the fields to change (`rating`, `notes`, `brewed_at`).

```json
{ "success": true, "log": { "id": 7, "rating": 4, "...": "..." } }
```

### DELETE /logs/&lt;id&gt;

Requires `delete:logs`.

```json
{ "success": true, "deleted": 7 }
```

## Deployment (Render)

`render.yaml` defines the web service and a Postgres database.

1. Push the repo to GitHub.
2. In Render, choose **New → Blueprint** and select the repo.
3. Set `AUTH0_DOMAIN` and `API_AUDIENCE` when prompted.

Migrations run during each build (`flask db upgrade`), and the app is served with `gunicorn "api:create_app()"`.
