"""Request body validation.

Each field maps to (required, validator). Validators return the cleaned
value, or abort with 422 and a message naming the field that's wrong.
"""
from datetime import datetime, timezone

from flask import abort, request

from models import (
    DRINK_TYPES,
    GRIND_MAX,
    GRIND_MIN,
    RATING_MAX,
    RATING_MIN,
    TEMP_MAX,
    TEMP_MIN,
)


def invalid(message):
    abort(422, description=message)


def whole_number(low=None, high=None):
    def validate(name, value):
        # bool is a subclass of int in Python, so reject it explicitly
        if isinstance(value, bool) or not isinstance(value, int):
            invalid(f"'{name}' must be a whole number")
        if low is not None and value < low:
            invalid(f"'{name}' must be at least {low}")
        if high is not None and value > high:
            invalid(f"'{name}' must be at most {high}")
        return value
    return validate


def text(required=False, max_length=None):
    def validate(name, value):
        if value is None:
            return None
        if not isinstance(value, str):
            invalid(f"'{name}' must be a string")
        value = value.strip()
        if required and not value:
            invalid(f"'{name}' must not be empty")
        if max_length and len(value) > max_length:
            invalid(f"'{name}' must be at most {max_length} characters")
        return value or None
    return validate


def drink_type(name, value):
    if value not in DRINK_TYPES:
        invalid(f"'{name}' must be one of: {', '.join(DRINK_TYPES)}")
    return value


def optional_id(name, value):
    if value is None:
        return None
    return whole_number(low=1)(name, value)


def iso_datetime(name, value):
    message = f"'{name}' must be an ISO 8601 date-time string"
    if not isinstance(value, str):
        invalid(message)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        invalid(message)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


RECIPE_FIELDS = {
    'beans': (True, text(required=True, max_length=200)),
    'coffee_grams': (True, whole_number(low=1)),
    'water_grams': (True, whole_number(low=1)),
    'water_temp': (True, whole_number(TEMP_MIN, TEMP_MAX)),
    'grind_setting': (True, whole_number(GRIND_MIN, GRIND_MAX)),
    'brew_time': (True, whole_number(low=1)),
    'drink_type': (True, drink_type),
    'instructions': (False, text()),
    'based_on_id': (False, optional_id),
    'adjustments': (False, text()),
}

LOG_FIELDS = {
    'rating': (True, whole_number(RATING_MIN, RATING_MAX)),
    'notes': (False, text()),
    # Can't be null, but may be omitted on create (defaults to now)
    'brewed_at': (True, iso_datetime),
}


def get_request_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description='Request body must be a JSON object')
    return body


def validate_body(body, fields, partial=False, optional_on_create=()):
    """Validate a request body against a field spec.

    partial=False (POST): every required field must be present.
    partial=True (PATCH): only the fields sent are validated, and at least
        one is needed.
    optional_on_create: required fields that may be omitted on POST
        because the model supplies a default.
    """
    unknown = set(body) - set(fields)
    if unknown:
        invalid(f"Unknown field(s): {', '.join(sorted(unknown))}")
    if partial and not body:
        abort(400, description='No fields provided to update')

    cleaned = {}
    for name, (required, validator) in fields.items():
        if name not in body:
            must_send = not partial and name not in optional_on_create
            if required and must_send:
                invalid(f"'{name}' is required")
            continue
        if body[name] is None and required:
            invalid(f"'{name}' must not be null")
        cleaned[name] = validator(name, body[name])
    return cleaned
