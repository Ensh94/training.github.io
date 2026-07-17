# Database Migration Guide

## What Changed

Your Flask app has been migrated from JSON file storage to PostgreSQL database for deployment on Render with persistent storage.

## Files Modified

1. **requirements.txt** - Added database dependencies:
   - Flask-SQLAlchemy==3.1.1
   - psycopg2-binary==2.9.9

2. **models.py** (NEW) - Database models for all data:
   - ShoppingState - Shopping list checked items
   - Recipe - Meal recipes
   - GymUser - Gym users
   - WorkoutProfile - Workout profiles
   - Exercise - Exercises in profiles
   - Workout - Completed workout sessions
   - ShoppingBackup - Shopping list backups
   - Feedback - User feedback
   - MealProfile - Meal profiles

3. **app.py** - Updated to use database:
   - ✅ Database configuration and initialization
   - ✅ Shopping state (load/save)
   - ✅ Recipes (load/add)
   - ✅ Backups (create/list/restore)
   - ✅ Gym users (get/add)
   - ✅ Feedback (save)
   - ✅ Meal profiles (get/add)
   - ⚠️ Gym workout profile endpoints - PARTIALLY UPDATED (still use JSON files)

4. **migrate_to_db.py** (NEW) - Migration script to move existing JSON data to database

## Testing Locally

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Run Migration (IMPORTANT - Back up your files first!)

```bash
python migrate_to_db.py
```

This will:
- Create a local SQLite database (`shopping_app.db`)
- Migrate all your existing JSON data to the database
- Preserve all shopping lists, recipes, gym profiles, workouts, etc.

### Step 3: Test the App Locally

```bash
python app.py
```

Visit http://localhost:2137 and test:
- ✅ Shopping list (check/uncheck items)
- ✅ Reset shopping list
- ✅ View backups
- ✅ Restore backups
- ✅ View recipes
- ✅ Add recipes
- ✅ Submit feedback
- ⚠️ Gym features (may have issues - see below)

## Known Issues

### Gym Endpoints Not Fully Updated

The gym/workout tracking features still use JSON file storage. These endpoints need to be updated:

- `/api/gym/<username>/profiles` (GET/POST)
- `/api/gym/<user_profile>/profiles/<profile_id>` (GET/PUT/DELETE)
- `/api/gym/<user_profile>/profiles/<profile_id>/exercises` (GET/POST)
- `/api/gym/<user_profile>/profiles/<profile_id>/exercises/<exercise_id>` (PUT/DELETE)
- `/api/gym/<user_profile>/profiles/<profile_id>/workouts` (GET/POST)
- And 20+ more gym-related endpoints...

**If you use the gym features**, they will continue to work with JSON files locally, but **data will NOT persist** when deployed to Render's free tier.

## Deploying to Render

### Step 1: Create PostgreSQL Database on Render

1. Go to https://dashboard.render.com/
2. Click "New +" → "PostgreSQL"
3. Choose a name (e.g., "shopping-app-db")
4. Select Free tier
5. Click "Create Database"
6. Copy the "Internal Database URL" (starts with `postgres://`)

### Step 2: Create Web Service

1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Configure:
   - **Root Directory**: *(leave empty)*
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance Type**: Free

### Step 3: Add Environment Variable

1. In your web service settings, go to "Environment"
2. Click "Add Environment Variable"
3. Add:
   - **Key**: `DATABASE_URL`
   - **Value**: *(paste the Internal Database URL from your PostgreSQL database)*

### Step 4: Deploy

1. Click "Manual Deploy" → "Deploy latest commit"
2. Wait for deployment to complete
3. Your app will be available at the Render URL

### Step 5: Migrate Production Data (Optional)

If you want to migrate your local data to production:

1. Install PostgreSQL locally
2. Update the migration script to use your production DATABASE_URL
3. Run the migration against production

**OR** simply start fresh - the app will create empty tables automatically.

## Database Connection

The app automatically:
- Uses SQLite locally (if no DATABASE_URL is set)
- Uses PostgreSQL on Render (via DATABASE_URL environment variable)
- Fixes Heroku/Render URL format (`postgres://` → `postgresql://`)

## Backup Your JSON Files!

Before deploying, make backups of:
- `shopping_state.json`
- `przepisy.json`
- `gym_data/` folder
- `backups/` folder
- `feedbacks/` folder
- `profiles.json`

## Next Steps to Complete Migration

If you want **full** database persistence for gym features:

1. Update remaining gym endpoints in app.py to use database models
2. Test thoroughly locally
3. Re-run migration to include workout data
4. Deploy to Render

## Testing Checklist

- [ ] Install dependencies
- [ ] Run migration script
- [ ] Test shopping list features
- [ ] Test recipe features
- [ ] Test backup/restore
- [ ] Test feedback submission
- [ ] Deploy to Render
- [ ] Test on production
- [ ] (Optional) Update gym endpoints

## Rollback Plan

If something goes wrong:
1. Your original JSON files are still intact
2. Delete `shopping_app.db`
3. Revert app.py changes using git
4. Run the original app

## Support

If you encounter issues:
1. Check terminal for error messages
2. Check Render logs (click "Logs" in your web service)
3. Verify DATABASE_URL is set correctly
4. Ensure all migrations completed successfully
