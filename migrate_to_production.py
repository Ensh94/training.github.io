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
local_engine = create_engine('sqlite:///instance/shopping_app.db')
LocalSession = sessionmaker(bind=local_engine)
local_session = LocalSession()

# Connect to PRODUCTION database
print("2. Connecting to production database...")
prod_engine = create_engine(production_db_url)
ProdSession = sessionmaker(bind=prod_engine)
prod_session = ProdSession()

# Create tables in production if they don't exist
print("3. Creating tables in production database...")
from app import app
app.config['SQLALCHEMY_DATABASE_URI'] = production_db_url
with app.app_context():
    # Drop all tables first to ensure schema matches
    print("   → Dropping existing tables (if any)...")
    db.drop_all()
    print("   → Creating fresh tables with correct schema...")
    db.create_all()
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
