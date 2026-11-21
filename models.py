import os
from datetime import datetime, timezone

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)

database_path = os.environ.get('DATABASE_URL', '')

db = SQLAlchemy()
migrate = Migrate()

DRINK_TYPES = ('hot', 'iced', 'espresso')
GRIND_MIN, GRIND_MAX = 1, 40     # Baratza Encore ESP settings
TEMP_MIN, TEMP_MAX = 32, 212     # Water temperature, degrees Fahrenheit
RATING_MIN, RATING_MAX = 1, 5


def normalize_database_url(url):
    """Point Postgres URLs at the psycopg2 driver.

    SQLAlchemy 2.1 defaults "postgresql://" to psycopg (v3), and Render
    hands out the legacy "postgres://" scheme, which SQLAlchemy rejects.
    """
    for prefix in ('postgres://', 'postgresql://'):
        if url.startswith(prefix):
            return 'postgresql+psycopg2://' + url[len(prefix):]
    return url


def setup_db(app, database_path=database_path):
    """Bind a Flask application to SQLAlchemy and Flask-Migrate."""
    app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_url(
        database_path)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    migrate.init_app(app, db)


class BaseModel(db.Model):
    """Shared insert/update/delete helpers."""
    __abstract__ = True

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def update(self):
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()


class Recipe(BaseModel):
    """A fixed set of brew parameters.

    Changing any parameter means a new recipe, optionally linked to the
    recipe it was tweaked from via based_on_id.
    """
    __tablename__ = 'recipes'

    id = Column(Integer, primary_key=True)
    beans = Column(String(200), nullable=False)
    coffee_grams = Column(Integer, nullable=False)
    water_grams = Column(Integer, nullable=False)
    water_temp = Column(Integer, nullable=False)      # Fahrenheit
    grind_setting = Column(Integer, nullable=False)   # Encore ESP, 1-40
    brew_time = Column(Integer, nullable=False)       # seconds
    drink_type = Column(
        Enum(*DRINK_TYPES, name='drink_type'), nullable=False)
    instructions = Column(Text)
    based_on_id = Column(
        Integer, ForeignKey('recipes.id', ondelete='SET NULL'))
    adjustments = Column(Text)

    logs = db.relationship(
        'Log',
        backref='recipe',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='Log.brewed_at.desc()',
    )
    based_on = db.relationship(
        'Recipe',
        remote_side=[id],
        backref=db.backref('derived_recipes', passive_deletes=True),
    )

    __table_args__ = (
        CheckConstraint(coffee_grams > 0, name='ck_recipes_coffee_grams'),
        CheckConstraint(water_grams > 0, name='ck_recipes_water_grams'),
        CheckConstraint(water_temp.between(TEMP_MIN, TEMP_MAX),
                        name='ck_recipes_water_temp'),
        CheckConstraint(grind_setting.between(GRIND_MIN, GRIND_MAX),
                        name='ck_recipes_grind_setting'),
        CheckConstraint(brew_time > 0, name='ck_recipes_brew_time'),
    )

    def format(self):
        return {
            'id': self.id,
            'beans': self.beans,
            'coffee_grams': self.coffee_grams,
            'water_grams': self.water_grams,
            'water_temp': self.water_temp,
            'grind_setting': self.grind_setting,
            'brew_time': self.brew_time,
            'drink_type': self.drink_type,
            'instructions': self.instructions,
            'based_on_id': self.based_on_id,
            'adjustments': self.adjustments,
        }


def _utcnow():
    return datetime.now(timezone.utc)


def _as_utc(value):
    """Report timestamps in UTC.

    Postgres returns timestamptz values in the server's time zone.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class Log(BaseModel):
    """One attempt at brewing a recipe, with the result."""
    __tablename__ = 'logs'

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer,
        ForeignKey('recipes.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    brewed_at = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow)
    rating = Column(Integer, nullable=False)
    notes = Column(Text)

    __table_args__ = (
        CheckConstraint(rating.between(RATING_MIN, RATING_MAX),
                        name='ck_logs_rating'),
    )

    def format(self):
        return {
            'id': self.id,
            'recipe_id': self.recipe_id,
            'brewed_at': _as_utc(self.brewed_at).isoformat(),
            'rating': self.rating,
            'notes': self.notes,
        }
