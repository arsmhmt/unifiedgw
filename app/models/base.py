from datetime import datetime
# Import db directly from the app's main __init__.py where it is now globally exposed
# after being initialized with the Flask app.
from ..extensions import db
from ..utils.timezone import now_eest

__all__ = ['BaseModel']

class BaseModel(db.Model):
    """Base model class that other models inherit from"""
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=now_eest)
    updated_at = db.Column(db.DateTime, default=now_eest, onupdate=now_eest)
    
    # Removed custom __init__ method. SQLAlchemy's declarative base handles this.
    # The __init__ method you had was overriding SQLAlchemy's default constructor
    # and trying to re-import 'db' from app.extensions, which is no longer the correct
    # source for the bound 'db' instance after the app/__init__.py refactor.
    
    def save(self):
        """Save the model instance to the database"""
        # Use the globally available 'db.session' which Flask-SQLAlchemy
        # binds to the current application context.
        db.session.add(self)
        db.session.commit()
        return self
    
    def delete(self):
        """Delete the model instance from the database"""
        db.session.delete(self)
        db.session.commit()
        return self
    
    def update(self, **kwargs):
        """Update model attributes and save to database"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()
        return self

