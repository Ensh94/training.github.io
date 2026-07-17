"""
Migration script to move JSON data to database
Run this script to migrate all existing JSON data to the database
"""
import json
import os
import glob
from app import app, db
from models import (ShoppingState, Recipe, GymUser, WorkoutProfile, Exercise, 
                   Workout, ShoppingBackup, Feedback, MealProfile)
from datetime import datetime

def migrate_shopping_state():
    """Migrate shopping state from JSON to database"""
    print("Migrating shopping state...")
    state_file = 'shopping_state.json'
    
    if not os.path.exists(state_file):
        print("No shopping state file found, skipping...")
        return
    
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    
    for item_id, checked in state.items():
        shopping_item = ShoppingState(item_id=item_id, checked=checked)
        db.session.add(shopping_item)
    
    db.session.commit()
    print(f"Migrated {len(state)} shopping state items")

def migrate_recipes():
    """Migrate recipes from JSON to database"""
    print("Migrating recipes...")
    recipes_file = 'przepisy.json'
    
    if not os.path.exists(recipes_file):
        print("No recipes file found, skipping...")
        return
    
    with open(recipes_file, 'r', encoding='utf-8') as f:
        recipes = json.load(f)
    
    count = 0
    for recipe_data in recipes:
        recipe = Recipe(
            name=recipe_data.get('name'),
            meal_type=recipe_data.get('meal_type'),
            day=recipe_data.get('day'),
            kcal=recipe_data.get('kcal'),
            time=recipe_data.get('time'),
            ingredients=json.dumps(recipe_data.get('ingredients', []), ensure_ascii=False),
            instructions=json.dumps(recipe_data.get('instructions', []), ensure_ascii=False)
        )
        db.session.add(recipe)
        count += 1
    
    db.session.commit()
    print(f"Migrated {count} recipes")

def migrate_backups():
    """Migrate backup files to database"""
    print("Migrating backups...")
    backup_dir = 'backups'
    
    if not os.path.exists(backup_dir):
        print("No backups directory found, skipping...")
        return
    
    count = 0
    for backup_file in glob.glob(os.path.join(backup_dir, 'backup_*.json')):
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        filename = os.path.basename(backup_file)
        timestamp_str = data.get('readable_date', data.get('timestamp'))
        
        # Parse timestamp
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        except:
            timestamp = datetime.now()
        
        backup = ShoppingBackup(
            filename=filename,
            timestamp=timestamp,
            state_data=json.dumps(data.get('state', {}), ensure_ascii=False),
            items_count=len(data.get('state', {}))
        )
        db.session.add(backup)
        count += 1
    
    db.session.commit()
    print(f"Migrated {count} backups")

def migrate_gym_users():
    """Migrate gym users from JSON to database"""
    print("Migrating gym users...")
    users_file = 'gym_data/users.json'
    
    if not os.path.exists(users_file):
        print("No gym users file found, creating defaults...")
        # Create default users
        for username in ['Łysy', 'Gość']:
            user = GymUser(username=username)
            db.session.add(user)
        db.session.commit()
        return
    
    with open(users_file, 'r', encoding='utf-8') as f:
        users = json.load(f)
    
    for username in users:
        user = GymUser(username=username)
        db.session.add(user)
    
    db.session.commit()
    print(f"Migrated {len(users)} gym users")

def migrate_workout_profiles():
    """Migrate workout profiles from JSON to database"""
    print("Migrating workout profiles...")
    gym_data_dir = 'gym_data'
    
    if not os.path.exists(gym_data_dir):
        print("No gym_data directory found, skipping...")
        return
    
    # Find all user profile files
    profile_files = glob.glob(os.path.join(gym_data_dir, '*.json'))
    profile_files = [f for f in profile_files if not f.endswith('_workouts.json') and not f.endswith('users.json')]
    
    total_profiles = 0
    total_exercises = 0
    
    for profile_file in profile_files:
        username = os.path.basename(profile_file).replace('.json', '')
        
        # Get or create user
        user = GymUser.query.filter_by(username=username).first()
        if not user:
            user = GymUser(username=username)
            db.session.add(user)
            db.session.commit()
        
        with open(profile_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        for profile_data in user_data.get('profiles', []):
            profile = WorkoutProfile(
                id=profile_data['id'],
                user_id=user.id,
                name=profile_data['name'],
                icon=profile_data.get('icon', '🏋️')
            )
            db.session.add(profile)
            total_profiles += 1
            
            # Add exercises
            for idx, exercise_data in enumerate(profile_data.get('exercises', [])):
                exercise = Exercise(
                    id=exercise_data['id'],
                    profile_id=profile.id,
                    name=exercise_data['name'],
                    info=exercise_data.get('info', ''),
                    recommended_sets=exercise_data.get('recommended_sets'),
                    recommended_reps=exercise_data.get('recommended_reps'),
                    parameters=json.dumps(exercise_data.get('parameters', []), ensure_ascii=False),
                    order_index=idx
                )
                db.session.add(exercise)
                total_exercises += 1
    
    db.session.commit()
    print(f"Migrated {total_profiles} workout profiles with {total_exercises} exercises")

def migrate_workouts():
    """Migrate workout sessions from JSON to database"""
    print("Migrating workout sessions...")
    gym_data_dir = 'gym_data'
    
    if not os.path.exists(gym_data_dir):
        print("No gym_data directory found, skipping...")
        return
    
    # Find all workout files
    workout_files = glob.glob(os.path.join(gym_data_dir, '*_workouts.json'))
    
    total_workouts = 0
    
    for workout_file in workout_files:
        with open(workout_file, 'r', encoding='utf-8') as f:
            workouts = json.load(f)
        
        for workout_data in workouts:
            # Parse date
            date_str = workout_data.get('date')
            if date_str:
                try:
                    workout_date = datetime.fromisoformat(date_str)
                except:
                    workout_date = datetime.now()
            else:
                workout_date = datetime.now()
            
            workout = Workout(
                id=workout_data.get('id', str(datetime.now().timestamp())),
                profile_id=workout_data.get('profile_id', workout_data.get('workout_profile_id')),
                user_profile=workout_data.get('user_profile'),
                workout_profile_id=workout_data.get('workout_profile_id'),
                date=workout_date,
                exercises_data=json.dumps(workout_data.get('exercises', []), ensure_ascii=False)
            )
            db.session.add(workout)
            total_workouts += 1
    
    db.session.commit()
    print(f"Migrated {total_workouts} workout sessions")

def migrate_meal_profiles():
    """Migrate meal profiles from JSON to database"""
    print("Migrating meal profiles...")
    profiles_file = 'profiles.json'
    
    if not os.path.exists(profiles_file):
        print("No profiles file found, creating default...")
        profile = MealProfile(name='Gość')
        db.session.add(profile)
        db.session.commit()
        return
    
    with open(profiles_file, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    
    for profile_name in profiles:
        profile = MealProfile(name=profile_name)
        db.session.add(profile)
    
    db.session.commit()
    print(f"Migrated {len(profiles)} meal profiles")

def migrate_feedback():
    """Migrate feedback files to database"""
    print("Migrating feedback...")
    feedback_dir = 'feedbacks'
    
    if not os.path.exists(feedback_dir):
        print("No feedbacks directory found, skipping...")
        return
    
    count = 0
    for feedback_file in glob.glob(os.path.join(feedback_dir, 'feedback_*.txt')):
        with open(feedback_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Extract date from text if possible
        lines = text.split('\n')
        created_at = datetime.now()
        
        if lines and lines[0].startswith('Data:'):
            try:
                date_str = lines[0].replace('Data:', '').strip()
                created_at = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        # Get actual feedback text (skip header lines)
        feedback_text = '\n'.join(lines[2:]) if len(lines) > 2 else text
        
        feedback = Feedback(text=feedback_text, created_at=created_at)
        db.session.add(feedback)
        count += 1
    
    db.session.commit()
    print(f"Migrated {count} feedback entries")

def run_migration():
    """Run all migrations"""
    print("=" * 50)
    print("Starting database migration...")
    print("=" * 50)
    
    with app.app_context():
        # Clear existing data
        print("\nClearing existing database data...")
        db.drop_all()
        db.create_all()
        print("Database tables created")
        
        # Run migrations
        migrate_shopping_state()
        migrate_recipes()
        migrate_backups()
        migrate_gym_users()
        migrate_workout_profiles()
        migrate_workouts()
        migrate_meal_profiles()
        migrate_feedback()
        
        print("\n" + "=" * 50)
        print("Migration completed successfully!")
        print("=" * 50)

if __name__ == '__main__':
    run_migration()
