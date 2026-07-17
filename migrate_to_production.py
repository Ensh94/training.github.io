"""
Migrate local database to production Render database
Run this ONCE after initial deployment to copy all your data to production
"""
import os
import sys

# Get production database URL from user
print("=" * 60)
print("MIGRATE LOCAL DATA TO PRODUCTION DATABASE")
print("=" * 60)
print("\nThis script will copy all your local data to your Render database.")
print("\n⚠️  WARNING: This will overwrite any existing data in production!")
print("\nTo proceed, you need:")
print("1. Your Render PostgreSQL 'Internal Database URL'")
print("2. Found in: Render Dashboard → Your Database → Connection → Internal Database URL")
print("\nExample URL format:")
print("postgres://user:password@hostname/database")
print("\n" + "=" * 60)

production_db_url = input("\nPaste your production DATABASE_URL here (or 'quit' to exit):\n> ").strip()

if production_db_url.lower() in ['quit', 'exit', 'q', '']:
    print("Migration cancelled.")
    sys.exit(0)

# Validate URL format
if not production_db_url.startswith(('postgres://', 'postgresql://')):
    print("\n❌ ERROR: Invalid database URL. Must start with postgres:// or postgresql://")
    sys.exit(1)

# Fix URL format if needed
if production_db_url.startswith('postgres://'):
    production_db_url = production_db_url.replace('postgres://', 'postgresql://', 1)

print("\n✓ Database URL accepted")
print("\nStarting migration in 3 seconds... (Press Ctrl+C to cancel)")

import time
try:
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\nMigration cancelled by user.")
    sys.exit(0)

print("\n" + "=" * 60)
print("MIGRATING DATA...")
print("=" * 60)

# Now do the actual migration
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import (ShoppingState, Recipe, GymUser, WorkoutProfile, Exercise, 
                   Workout, ShoppingBackup, Feedback, MealProfile, db)
import json

# Connect to LOCAL database
print("\n1. Connecting to local database...")
local_db_path = os.path.join(os.path.dirname(__file__), 'instance', 'shopping_app.db')
print(f"   Local DB path: {local_db_path}")
local_engine = create_engine(f'sqlite:///{local_db_path}')
LocalSession = sessionmaker(bind=local_engine)
local_session = LocalSession()

# Connect to PRODUCTION database
print("2. Connecting to production database...")
prod_engine = create_engine(production_db_url)
ProdSession = sessionmaker(bind=prod_engine)
prod_session = ProdSession()

# Print source counts so we can verify migration input before copying
print("3. Verifying source (local) row counts...")
print(f"   → Recipes: {local_session.query(Recipe).count()}")
print(f"   → Meal profiles: {local_session.query(MealProfile).count()}")
print(f"   → Gym users: {local_session.query(GymUser).count()}")
print(f"   → Workout profiles: {local_session.query(WorkoutProfile).count()}")
print(f"   → Exercises: {local_session.query(Exercise).count()}")
print(f"   → Workouts: {local_session.query(Workout).count()}")
print(f"   → Backups: {local_session.query(ShoppingBackup).count()}")
print(f"   → Feedback: {local_session.query(Feedback).count()}")

# Recreate schema in production only
print("3. Creating tables in production database...")
print("   → Dropping existing tables (if any) on PRODUCTION...")
db.Model.metadata.drop_all(bind=prod_engine)
print("   → Creating fresh tables with correct schema on PRODUCTION...")
db.Model.metadata.create_all(bind=prod_engine)
print("   ✓ Tables created successfully")

def copy_table(model, name):
    """Copy data from local to production for a given model"""
    print(f"\n4. Migrating {name}...")
    local_items = local_session.query(model).all()
    
    if not local_items:
        print(f"   → No {name} to migrate")
        return 0
    
    count = 0
    for item in local_items:
        # Create a dictionary of all columns
        item_dict = {c.name: getattr(item, c.name) for c in item.__table__.columns}

        # Legacy data fix: some workouts point to profile names instead of profile IDs.
        if model is Workout:
            profile_id = item_dict.get('profile_id')
            workout_profile_id = item_dict.get('workout_profile_id')
            user_profile = item_dict.get('user_profile') or 'Gość'

            # 1) If profile_id does not exist, try workout_profile_id as canonical profile reference.
            if profile_id:
                profile_exists = prod_session.query(WorkoutProfile).filter_by(id=profile_id).first()
            else:
                profile_exists = None

            if not profile_exists and workout_profile_id:
                alt_profile = prod_session.query(WorkoutProfile).filter_by(id=workout_profile_id).first()
                if alt_profile:
                    item_dict['profile_id'] = workout_profile_id
                    profile_exists = alt_profile

            # 2) If still missing, create a placeholder profile so FK remains valid.
            if not profile_exists:
                placeholder_profile_id = item_dict.get('profile_id') or workout_profile_id or f"legacy_{item_dict.get('id')}"

                # Ensure owner user exists.
                owner = prod_session.query(GymUser).filter_by(username=user_profile).first()
                if not owner:
                    owner = GymUser(username=user_profile)
                    prod_session.add(owner)
                    prod_session.flush()

                existing_placeholder = prod_session.query(WorkoutProfile).filter_by(id=placeholder_profile_id).first()
                if not existing_placeholder:
                    existing_placeholder = WorkoutProfile(
                        id=placeholder_profile_id,
                        user_id=owner.id,
                        name=f"Legacy {placeholder_profile_id}",
                        icon='🏋️'
                    )
                    prod_session.add(existing_placeholder)
                    prod_session.flush()

                item_dict['profile_id'] = placeholder_profile_id
        
        # Check if item already exists in production (by primary key)
        pk_cols = [c.name for c in item.__table__.primary_key.columns]
        pk_values = {col: item_dict[col] for col in pk_cols}
        
        existing = prod_session.query(model).filter_by(**pk_values).first()
        
        if existing:
            # Update existing item
            for key, value in item_dict.items():
                setattr(existing, key, value)
        else:
            # Create new item
            new_item = model(**item_dict)
            prod_session.add(new_item)
        
        count += 1
    
    prod_session.commit()
    print(f"   ✓ Migrated {count} {name}")
    return count

# Migrate all tables
total = 0
total += copy_table(ShoppingState, "shopping state items")
total += copy_table(Recipe, "recipes")
total += copy_table(ShoppingBackup, "backups")
total += copy_table(Feedback, "feedback entries")
total += copy_table(MealProfile, "meal profiles")
total += copy_table(GymUser, "gym users")
total += copy_table(WorkoutProfile, "workout profiles")
total += copy_table(Exercise, "exercises")
total += copy_table(Workout, "workout sessions")

# Close connections
local_session.close()
prod_session.close()

print("\n" + "=" * 60)
print(f"✅ MIGRATION COMPLETED SUCCESSFULLY!")
print(f"   Total items migrated: {total}")
print("=" * 60)
print("\nYour production app should now have all your data!")
print("Visit your Render app URL to verify.\n")
