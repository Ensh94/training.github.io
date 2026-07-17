from app import app, db
from models import Recipe, GymUser, MealProfile

with app.app_context():
    print('Recipes:', Recipe.query.count())
    print('Gym Users:', GymUser.query.count())
    print('Meal Profiles:', MealProfile.query.count())
