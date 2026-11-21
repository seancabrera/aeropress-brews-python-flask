"""Helpers shared by the controllers."""
from flask import abort
from sqlalchemy import exc

from models import db


def get_or_404(model, item_id):
    """Fetch a row by primary key, or abort with 404."""
    item = db.session.get(model, item_id)
    if item is None:
        abort(404, description=f'{model.__name__} {item_id} not found')
    return item


def commit_or_422(save):
    """Run a model's insert/update/delete, turning DB errors into a 422.

    Validation catches bad input first; this is the safety net for
    anything the database still rejects (e.g. a check constraint).
    """
    try:
        save()
    except exc.SQLAlchemyError:
        db.session.rollback()
        abort(422, description='The database rejected the change')
