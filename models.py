from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class ShoppingState(db.Model):
    """Stores the checked/unchecked state of shopping list items"""
    __tablename__ = 'shopping_state'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(500), unique=True, nullable=False)
    checked = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Recipe(db.Model):
    """Stores recipes (przepisy)"""
    __tablename__ = 'recipes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    meal_type = db.Column(db.String(100), nullable=False)  # Śniadanie, Drugie śniadanie, etc.
    day = db.Column(db.String(100))  # Date with day name in Polish
    kcal = db.Column(db.String(50))
    time = db.Column(db.String(50))
    ingredients = db.Column(db.Text)  # JSON array as text
    instructions = db.Column(db.Text)  # JSON array as text
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'meal_type': self.meal_type,
            'day': self.day,
            'kcal': self.kcal,
            'time': self.time,
            'ingredients': json.loads(self.ingredients) if self.ingredients else [],
            'instructions': json.loads(self.instructions) if self.instructions else []
        }

class GymUser(db.Model):
    """Stores gym users"""
    __tablename__ = 'gym_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    workout_profiles = db.relationship('WorkoutProfile', backref='user', lazy=True, cascade='all, delete-orphan')

class WorkoutProfile(db.Model):
    """Stores workout profiles for users"""
    __tablename__ = 'workout_profiles'
    
    id = db.Column(db.String(100), primary_key=True)  # Using string ID for compatibility
    user_id = db.Column(db.Integer, db.ForeignKey('gym_users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(10), default='🏋️')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    exercises = db.relationship('Exercise', backref='profile', lazy=True, cascade='all, delete-orphan', order_by='Exercise.order_index')
    workouts = db.relationship('Workout', backref='profile', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'icon': self.icon,
            'exercises': [ex.to_dict() for ex in self.exercises]
        }

class Exercise(db.Model):
    """Stores exercises in workout profiles"""
    __tablename__ = 'exercises'
    
    id = db.Column(db.String(100), primary_key=True)
    profile_id = db.Column(db.String(100), db.ForeignKey('workout_profiles.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    info = db.Column(db.Text, default='')
    recommended_sets = db.Column(db.String(50))
    recommended_reps = db.Column(db.String(50))
    parameters = db.Column(db.Text)  # JSON array: ['weight', 'reps', 'sets', etc.]
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'info': self.info,
            'recommended_sets': self.recommended_sets,
            'recommended_reps': self.recommended_reps,
            'parameters': json.loads(self.parameters) if self.parameters else [],
            'results': []  # Results are stored in Workout model
        }

class Workout(db.Model):
    """Stores completed workout sessions"""
    __tablename__ = 'workouts'
    
    id = db.Column(db.String(100), primary_key=True)
    profile_id = db.Column(db.String(100), db.ForeignKey('workout_profiles.id'), nullable=False)
    user_profile = db.Column(db.String(100))  # For new API compatibility
    workout_profile_id = db.Column(db.String(100))  # For new API compatibility
    date = db.Column(db.DateTime, default=datetime.utcnow)
    exercises_data = db.Column(db.Text)  # JSON data of completed exercises
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'user_profile': self.user_profile,
            'workout_profile_id': self.workout_profile_id,
            'date': self.date.isoformat() if self.date else None,
            'exercises': json.loads(self.exercises_data) if self.exercises_data else []
        }

class ShoppingBackup(db.Model):
    """Stores backups of shopping list state"""
    __tablename__ = 'shopping_backups'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    state_data = db.Column(db.Text)  # JSON data
    items_count = db.Column(db.Integer, default=0)
    
    def to_dict(self):
        return {
            'filename': self.filename,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'items_count': self.items_count
        }

class Feedback(db.Model):
    """Stores user feedback"""
    __tablename__ = 'feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MealProfile(db.Model):
    """Stores meal profiles"""
    __tablename__ = 'meal_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
