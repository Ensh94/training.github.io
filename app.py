from flask import Flask, render_template, request, jsonify
import json
import os
import time
from datetime import datetime
import glob
from models import db, ShoppingState, Recipe, GymUser, WorkoutProfile, Exercise, Workout, ShoppingBackup, Feedback, MealProfile

app = Flask(__name__)

# Database configuration
# Use absolute path for SQLite in instance folder
if os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
else:
    # Local development - use instance folder
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'shopping_app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

# Fix for Heroku/Render PostgreSQL URLs
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()

# Legacy file paths (for migration purposes)
STATE_FILE = 'shopping_state.json'
BACKUP_DIR = 'backups'

def load_shopping_list():
    """Wczytuje listę zakupów z pliku tekstowego"""
    items = {}
    current_category = None
    
    with open('lista_zakupow_29_12_01_01.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # Pomijamy puste linie i dekoracje
            if not line or line.startswith('═') or line == 'LISTA ZAKUPÓW' or line == '29 grudnia - 01 stycznia':
                continue
            
            # Sprawdzamy czy to kategoria (duże litery, bez checkbox)
            if line.isupper() and not line.startswith('□'):
                current_category = line
                if current_category not in items:
                    items[current_category] = []
            # Sprawdzamy czy to przedmiot (zaczyna się od □)
            elif line.startswith('□') and current_category:
                item_text = line[2:].strip()  # Usuwamy □ i spacje
                items[current_category].append(item_text)
    
    # Wczytaj stan zaznaczenia
    state = load_state()
    
    # Sortuj kategorie: najpierw te z niezakupionymi produktami (alfabetycznie), potem te kompletne (alfabetycznie)
    def category_sort_key(cat_tuple):
        category, products = cat_tuple
        # Sprawdź czy wszystkie produkty w kategorii są kupione
        all_bought = all(state.get(f"{category}::{product}", False) for product in products)
        # Zwróć tuple: (czy_wszystko_kupione, nazwa_kategorii)
        # False będzie przed True (niekompletne kategorie na górze)
        return (all_bought, category)
    
    sorted_items = dict(sorted(items.items(), key=category_sort_key))
    
    # Sortuj produkty w każdej kategorii: najpierw niezakupione (alfabetycznie), potem zakupione (alfabetycznie)
    for category in sorted_items:
        def product_sort_key(product):
            is_bought = state.get(f"{category}::{product}", False)
            # Zwróć tuple: (czy_kupione, nazwa_produktu)
            return (is_bought, product)
        
        sorted_items[category] = sorted(sorted_items[category], key=product_sort_key)
    
    return sorted_items

def load_state():
    """Wczytuje stan zaznaczonych przedmiotów z bazy danych"""
    items = ShoppingState.query.all()
    return {item.item_id: item.checked for item in items}

def save_state(state):
    """Zapisuje stan zaznaczonych przedmiotów do bazy danych"""
    for item_id, checked in state.items():
        item = ShoppingState.query.filter_by(item_id=item_id).first()
        if item:
            item.checked = checked
            item.updated_at = datetime.utcnow()
        else:
            item = ShoppingState(item_id=item_id, checked=checked)
            db.session.add(item)
    db.session.commit()

def load_przepisy():
    """Wczytuje przepisy z bazy danych"""
    recipes = Recipe.query.all()
    return [r.to_dict() for r in recipes]

def save_przepisy(przepisy):
    """Zapisuje przepisy do bazy danych - nie używane, używamy add_recipe"""
    pass  # Legacy function, kept for compatibility

def get_current_meal_type():
    """Określa typ posiłku na podstawie aktualnej godziny"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    time_in_minutes = hour * 60 + minute
    
    # Przedziały czasowe w minutach
    if 0 <= time_in_minutes <= 540:  # 00:00-09:00
        return "Śniadanie"
    elif 541 <= time_in_minutes <= 780:  # 09:01-13:00
        return "Drugie śniadanie"
    elif 781 <= time_in_minutes <= 1050:  # 13:01-17:30
        return "Obiad"
    elif 1051 <= time_in_minutes <= 1170:  # 17:31-19:30
        return "Podwieczorek"
    else:  # 19:31-23:59
        return "Kolacja"

def get_meal_context():
    """Zwraca poprzedni, aktualny i następny posiłek"""
    meal_order = ["Śniadanie", "Drugie śniadanie", "Obiad", "Podwieczorek", "Kolacja"]
    current_type = get_current_meal_type()
    current_index = meal_order.index(current_type)
    
    # Dzisiejsza data
    today = datetime.now().strftime('%d.%m.%Y')
    
    # Wczytaj wszystkie przepisy
    all_recipes = load_przepisy()
    
    # Znajdź przepisy na dziś
    today_recipes = [r for r in all_recipes if today in r['day']]
    
    # Jeśli nie ma na dziś, weź pierwsze dostępne
    if not today_recipes:
        today_recipes = all_recipes[:5] if len(all_recipes) >= 5 else all_recipes
    
    # Znajdź przepisy według typu posiłku
    def find_recipe_by_type(meal_type):
        for recipe in today_recipes:
            if recipe['meal_type'] == meal_type:
                return recipe
        return None
    
    current_meal = find_recipe_by_type(current_type)
    previous_meal = find_recipe_by_type(meal_order[current_index - 1]) if current_index > 0 else None
    next_meal = find_recipe_by_type(meal_order[current_index + 1]) if current_index < len(meal_order) - 1 else None
    
    return {
        'previous': previous_meal,
        'current': current_meal,
        'next': next_meal,
        'current_type': current_type
    }

@app.route('/api/meals')
def get_all_meals():
    """Zwraca wszystkie posiłki na dziś w odpowiedniej kolejności"""
    meal_order = ["Śniadanie", "Drugie śniadanie", "Obiad", "Podwieczorek", "Kolacja"]
    today = datetime.now().strftime('%d.%m.%Y')
    
    # Wczytaj wszystkie przepisy
    all_recipes = load_przepisy()
    
    # Znajdź przepisy na dziś
    today_recipes = [r for r in all_recipes if today in r['day']]
    
    # Jeśli nie ma na dziś, weź pierwsze dostępne
    if not today_recipes:
        today_recipes = all_recipes[:5] if len(all_recipes) >= 5 else all_recipes
    
    # Sortuj według kolejności posiłków
    sorted_meals = []
    for meal_type in meal_order:
        for recipe in today_recipes:
            if recipe['meal_type'] == meal_type:
                sorted_meals.append(recipe)
                break
    
    # Znalezienie aktualnego posiłku
    current_type = get_current_meal_type()
    current_index = next((i for i, meal in enumerate(sorted_meals) if meal['meal_type'] == current_type), 0)
    
    return jsonify({
        'meals': sorted_meals,
        'current_index': current_index
    })

def create_backup():
    """Tworzy backup aktualnego stanu w bazie danych"""
    state = load_state()
    if not state:  # Nie tworzymy backupu pustego stanu
        return None
    
    timestamp = datetime.now()
    filename = f'backup_{timestamp.strftime("%Y%m%d_%H%M%S")}.json'
    
    backup = ShoppingBackup(
        filename=filename,
        timestamp=timestamp,
        state_data=json.dumps(state, ensure_ascii=False),
        items_count=len(state)
    )
    db.session.add(backup)
    db.session.commit()
    
    return filename

def list_backups():
    """Listuje wszystkie dostępne backupy z bazy danych"""
    backups = ShoppingBackup.query.order_by(ShoppingBackup.timestamp.desc()).all()
    return [b.to_dict() for b in backups]

def restore_backup(filename):
    """Przywraca stan z backupu"""
    backup = ShoppingBackup.query.filter_by(filename=filename).first()
    if not backup:
        return False
    
    state = json.loads(backup.state_data)
    
    # Clear existing state
    ShoppingState.query.delete()
    
    # Restore from backup
    save_state(state)
    return True

@app.route('/')
def index():
    """Główna strona z listą zakupów"""
    items = load_shopping_list()
    state = load_state()
    meal_context = get_meal_context()
    return render_template('index.html', items=items, state=state, meal_context=meal_context)

@app.route('/api/toggle', methods=['POST'])
def toggle_item():
    """API do zaznaczania/odznaczania przedmiotów"""
    data = request.json
    item_id = data.get('item_id')
    checked = data.get('checked')
    
    state = load_state()
    state[item_id] = checked
    save_state(state)
    
    return jsonify({'success': True, 'item_id': item_id, 'checked': checked})

@app.route('/api/reset', methods=['POST'])
def reset_state():
    """API do resetowania całej listy"""
    # Twórz backup przed resetem
    backup_file = create_backup()
    save_state({})
    return jsonify({
        'success': True,
        'backup_created': backup_file is not None,
        'backup_file': os.path.basename(backup_file) if backup_file else None
    })

@app.route('/api/przepisy', methods=['GET'])
def get_przepisy():
    """API do pobierania przepisów"""
    przepisy = load_przepisy()
    
    # Usuń duplikaty - zachowaj tylko pierwsze wystąpienie każdego przepisu
    seen = set()
    unique_przepisy = []
    for przepis in przepisy:
        recipe_key = (przepis.get('name'), przepis.get('meal_type'))
        if recipe_key not in seen:
            seen.add(recipe_key)
            unique_przepisy.append(przepis)
    
    return jsonify(unique_przepisy)

@app.route('/api/recipes/add', methods=['POST'])
def add_recipe():
    """API do dodawania nowego przepisu"""
    try:
        new_recipe = request.json
        
        # Walidacja wymaganych pól
        required_fields = ['name', 'meal_type', 'kcal', 'time', 'ingredients', 'instructions']
        for field in required_fields:
            if field not in new_recipe:
                return jsonify({'success': False, 'error': f'Brak wymaganego pola: {field}'}), 400
        
        # Utwórz nowy przepis w bazie danych
        recipe = Recipe(
            name=new_recipe['name'],
            meal_type=new_recipe['meal_type'],
            day=new_recipe.get('day'),
            kcal=new_recipe['kcal'],
            time=new_recipe['time'],
            ingredients=json.dumps(new_recipe['ingredients'], ensure_ascii=False),
            instructions=json.dumps(new_recipe['instructions'], ensure_ascii=False)
        )
        db.session.add(recipe)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Przepis został dodany'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/backups', methods=['GET'])
def get_backups():
    """API do listowania backupów"""
    backups = list_backups()
    return jsonify(backups)

@app.route('/api/restore/<filename>', methods=['POST'])
def restore_backup_endpoint(filename):
    """API do przywracania backupu"""
    success = restore_backup(filename)
    return jsonify({'success': success})

# ===== GYM ENDPOINTS =====
GYM_DATA_DIR = 'gym_data'

# ===== GYM ENDPOINTS =====
GYM_DATA_DIR = 'gym_data'  # Legacy, kept for reference

def ensure_gym_dir():
    """Tworzy katalog gym_data dla legacy endpointow opartych o pliki JSON."""
    if not os.path.exists(GYM_DATA_DIR):
        os.makedirs(GYM_DATA_DIR)

@app.route('/api/gym/users', methods=['GET'])
def get_gym_users():
    """Zwraca listę użytkowników z bazy danych"""
    users = GymUser.query.all()
    if not users:
        # Tworzymy domyślnych użytkowników
        default_users = ['Łysy', 'Gość']
        for username in default_users:
            user = GymUser(username=username)
            db.session.add(user)
        db.session.commit()
        return jsonify(default_users)
    
    return jsonify([user.username for user in users])

@app.route('/api/gym/users', methods=['POST'])
def add_gym_user():
    """Dodaje nowego użytkownika do bazy danych"""
    data = request.json
    username = data.get('username')
    
    if not username:
        return jsonify({'success': False, 'error': 'Username required'})
    
    # Check if user already exists
    existing_user = GymUser.query.filter_by(username=username).first()
    if existing_user:
        users = GymUser.query.all()
        return jsonify({'success': True, 'users': [u.username for u in users]})
    
    # Add new user
    new_user = GymUser(username=username)
    db.session.add(new_user)
    db.session.commit()
    
    users = GymUser.query.all()
    return jsonify({'success': True, 'users': [u.username for u in users]})

@app.route('/api/gym/<username>/profiles', methods=['GET'])
def get_user_profiles(username):
    """Zwraca profile ćwiczeń użytkownika"""
    ensure_gym_dir()
    user_file = os.path.join(GYM_DATA_DIR, f'{username}.json')
    
    if not os.path.exists(user_file):
        return jsonify([])
    
    with open(user_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return jsonify(data.get('profiles', []))

# Stary endpoint usunięty - obsługiwany przez nowy endpoint na linii 563

@app.route('/api/gym/<username>/profiles/<profile_id>/exercises', methods=['POST'])
def add_exercise(username, profile_id):
    """Dodaje ćwiczenie do profilu"""
    ensure_gym_dir()
    data = request.json
    
    user_file = os.path.join(GYM_DATA_DIR, f'{username}.json')
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    for profile in user_data['profiles']:
        if profile['id'] == profile_id:
            new_exercise = {
                'id': str(datetime.now().timestamp()),
                'name': data.get('name'),
                'info': data.get('info', ''),
                'recommended_sets': data.get('recommended_sets'),
                'recommended_reps': data.get('recommended_reps'),
                'parameters': data.get('parameters', []),  # ['weight', 'reps', 'sets', 'distance', 'time']
                'results': []
            }
            profile['exercises'].append(new_exercise)
            break
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<username>/profiles/<profile_id>/exercises/<exercise_id>/results', methods=['POST'])
def add_result(username, profile_id, exercise_id):
    """Dodaje wynik ćwiczenia"""
    ensure_gym_dir()
    data = request.json
    
    user_file = os.path.join(GYM_DATA_DIR, f'{username}.json')
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    for profile in user_data['profiles']:
        if profile['id'] == profile_id:
            for exercise in profile['exercises']:
                if exercise['id'] == exercise_id:
                    new_result = {
                        'id': str(datetime.now().timestamp()),
                        'date': datetime.now().isoformat(),
                        'values': data.get('values', {})
                    }
                    exercise['results'].append(new_result)
                    break
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<username>/profiles/<profile_id>', methods=['GET'])
def get_profile(username, profile_id):
    """Zwraca szczegóły profilu"""
    ensure_gym_dir()
    user_file = os.path.join(GYM_DATA_DIR, f'{username}.json')
    
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    for profile in user_data['profiles']:
        if profile['id'] == profile_id:
            return jsonify(profile)
    
    return jsonify({'error': 'Profile not found'}), 404

@app.route('/api/gym/<username>/profiles/<profile_id>', methods=['PUT'])
def update_profile(username, profile_id):
    """Aktualizuje profil"""
    ensure_gym_dir()
    data = request.json
    
    user_file = os.path.join(GYM_DATA_DIR, f'{username}.json')
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    for profile in user_data['profiles']:
        if profile['id'] == profile_id:
            profile['name'] = data.get('name', profile['name'])
            if 'icon' in data:
                profile['icon'] = data['icon']
            break
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<username>/profiles/<profile_id>/exercises/<exercise_id>', methods=['PUT'])
def update_exercise(username, profile_id, exercise_id):
    """Aktualizuje ćwiczenie"""
    ensure_gym_dir()
    data = request.json
    
    user_file = os.path.join(GYM_DATA_DIR, f'{username}.json')
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    for profile in user_data['profiles']:
        if profile['id'] == profile_id:
            for exercise in profile['exercises']:
                if exercise['id'] == exercise_id:
                    exercise['name'] = data.get('name', exercise['name'])
                    exercise['info'] = data.get('info', exercise.get('info', ''))
                    exercise['recommended_sets'] = data.get('recommended_sets', exercise.get('recommended_sets'))
                    exercise['recommended_reps'] = data.get('recommended_reps', exercise.get('recommended_reps'))
                    exercise['parameters'] = data.get('parameters', exercise['parameters'])
                    break
            break
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<username>/profiles/<profile_id>/exercises/reorder', methods=['PUT'])
def reorder_exercises(username, profile_id):
    """Zmienia kolejność ćwiczeń w profilu"""
    ensure_gym_dir()
    data = request.json
    exercise_ids = data.get('exercise_ids', [])
    
    user_file = os.path.join(GYM_DATA_DIR, f'{username}.json')
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    for profile in user_data['profiles']:
        if profile['id'] == profile_id:
            # Przesortuj ćwiczenia według podanej kolejności ID
            exercises_dict = {ex['id']: ex for ex in profile['exercises']}
            profile['exercises'] = [exercises_dict[ex_id] for ex_id in exercise_ids if ex_id in exercises_dict]
            break
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<username>/profiles/<profile_id>', methods=['DELETE'])
def delete_profile(username, profile_id):
    """Usuwa profil"""
    ensure_gym_dir()
    user_file = os.path.join(GYM_DATA_DIR, f'{username}.json')
    
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    user_data['profiles'] = [p for p in user_data['profiles'] if p['id'] != profile_id]
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<username>/profiles/<profile_id>/exercises/<exercise_id>', methods=['DELETE'])
def delete_exercise(username, profile_id, exercise_id):
    """Usuwa ćwiczenie"""
    ensure_gym_dir()
    user_file = os.path.join(GYM_DATA_DIR, f'{username}.json')
    
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    for profile in user_data['profiles']:
        if profile['id'] == profile_id:
            profile['exercises'] = [e for e in profile['exercises'] if e['id'] != exercise_id]
            break
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<username>/workouts', methods=['POST'])
def save_workout(username):
    """Zapisuje sesję treningową"""
    ensure_gym_dir()
    data = request.json
    
    data['id'] = str(datetime.now().timestamp())
    data['username'] = username
    
    workouts_file = os.path.join(GYM_DATA_DIR, f'{username}_workouts.json')
    workouts = []
    
    if os.path.exists(workouts_file):
        with open(workouts_file, 'r', encoding='utf-8') as f:
            workouts = json.load(f)
    
    workouts.append(data)
    
    with open(workouts_file, 'w', encoding='utf-8') as f:
        json.dump(workouts, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True, 'workout_id': data['id']})

@app.route('/api/gym/<username>/workouts/<profile_id>', methods=['GET'])
def get_workouts(username, profile_id):
    """Pobiera treningi dla danego profilu"""
    ensure_gym_dir()
    workouts_file = os.path.join(GYM_DATA_DIR, f'{username}_workouts.json')
    
    if not os.path.exists(workouts_file):
        return jsonify([])
    
    with open(workouts_file, 'r', encoding='utf-8') as f:
        all_workouts = json.load(f)
    
    profile_workouts = [w for w in all_workouts if w.get('profile_id') == profile_id]
    
    return jsonify(profile_workouts)

@app.route('/api/gym/<username>/workouts/<workout_id>', methods=['DELETE'])
def delete_workout(username, workout_id):
    """Usuwa trening"""
    ensure_gym_dir()
    workouts_file = os.path.join(GYM_DATA_DIR, f'{username}_workouts.json')
    
    if not os.path.exists(workouts_file):
        return jsonify({'success': False, 'error': 'No workouts file'})
    
    with open(workouts_file, 'r', encoding='utf-8') as f:
        workouts = json.load(f)
    
    # Filtruj - usuń trening o podanym ID
    workouts = [w for w in workouts if w.get('id') != workout_id]
    
    with open(workouts_file, 'w', encoding='utf-8') as f:
        json.dump(workouts, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

# ===== NOWE ENDPOINTY OPARTE NA PROFILACH =====

@app.route('/api/gym/<user_profile>/profiles', methods=['GET', 'POST'])
def user_workout_profiles(user_profile):
    """GET: Zwraca profile ćwiczeń użytkownika, POST: Dodaje nowy profil ćwiczeń"""
    ensure_gym_dir()
    user_file = os.path.join(GYM_DATA_DIR, f'{user_profile}.json')
    
    if request.method == 'GET':
        if not os.path.exists(user_file):
            return jsonify([])
        
        with open(user_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        return jsonify(user_data.get('profiles', []))
    
    elif request.method == 'POST':
        print("POST request received", flush=True)
        data = request.get_json()
        print(f"Received data: {data}", flush=True)
        print(f"Request content type: {request.content_type}", flush=True)
        print(f"Request data: {request.data}", flush=True)
        
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'}), 400
            
        name = data.get('name')
        icon = data.get('icon', '🏋️')
        
        print(f"Name: {name}, Icon: {icon}", flush=True)
        
        if not name:
            return jsonify({'success': False, 'error': 'Name is required'}), 400
        
        # Load or create user data
        if os.path.exists(user_file):
            with open(user_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
        else:
            user_data = {'profiles': []}
        
        # Create new profile
        new_profile = {
            'id': str(time.time()),
            'name': name,
            'icon': icon,
            'exercises': []
        }
        
        user_data['profiles'].append(new_profile)
        
        # Save
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True, 'profile': new_profile})

@app.route('/api/gym/<user_profile>/profiles/<profile_id>', methods=['GET', 'PUT', 'DELETE'])
def manage_workout_profile(user_profile, profile_id):
    """GET: Zwraca szczegóły profilu, PUT: Edytuje profil, DELETE: Usuwa profil"""
    ensure_gym_dir()
    user_file = os.path.join(GYM_DATA_DIR, f'{user_profile}.json')
    
    if request.method == 'GET':
        with open(user_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        for profile in user_data.get('profiles', []):
            if profile['id'] == profile_id:
                return jsonify(profile)
        
        return jsonify({'error': 'Profile not found'}), 404
    
    elif request.method == 'PUT':
        data = request.get_json()
        name = data.get('name')
        icon = data.get('icon')
        
        with open(user_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        for profile in user_data.get('profiles', []):
            if profile['id'] == profile_id:
                if name:
                    profile['name'] = name
                if icon:
                    profile['icon'] = icon
                
                with open(user_file, 'w', encoding='utf-8') as f:
                    json.dump(user_data, f, ensure_ascii=False, indent=2)
                
                return jsonify({'success': True, 'profile': profile})
        
        return jsonify({'success': False, 'error': 'Profile not found'}), 404
    
    elif request.method == 'DELETE':
        with open(user_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        user_data['profiles'] = [p for p in user_data.get('profiles', []) if p['id'] != profile_id]
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True})

@app.route('/api/gym/<user_profile>/profiles/<profile_id>/exercises', methods=['GET', 'POST'])
def workout_profile_exercises(user_profile, profile_id):
    """GET: Zwraca ćwiczenia profilu, POST: Dodaje ćwiczenie do profilu"""
    ensure_gym_dir()
    user_file = os.path.join(GYM_DATA_DIR, f'{user_profile}.json')
    
    if request.method == 'GET':
        with open(user_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        for profile in user_data.get('profiles', []):
            if profile['id'] == profile_id:
                return jsonify({'exercises': profile.get('exercises', [])})
        
        return jsonify({'exercises': []}), 404
    
    elif request.method == 'POST':
        data = request.json
        
        with open(user_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        for profile in user_data.get('profiles', []):
            if profile['id'] == profile_id:
                new_exercise = {
                    'id': str(int(time.time() * 1000)),
                    'name': data.get('name'),
                    'parameters': data.get('parameters', []),
                    'info': data.get('info', ''),
                    'recommended_sets': data.get('recommended_sets'),
                    'recommended_reps': data.get('recommended_reps'),
                    'results': []
                }
                profile['exercises'].append(new_exercise)
                break
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True, 'exercise': new_exercise})

@app.route('/api/gym/<user_profile>/profiles/<profile_id>/exercises/<exercise_id>', methods=['PUT'])
def update_workout_profile_exercise(user_profile, profile_id, exercise_id):
    """Aktualizuje ćwiczenie w profilu ćwiczeń"""
    ensure_gym_dir()
    data = request.json
    user_file = os.path.join(GYM_DATA_DIR, f'{user_profile}.json')
    
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    for profile in user_data.get('profiles', []):
        if profile['id'] == profile_id:
            for exercise in profile['exercises']:
                if exercise['id'] == exercise_id:
                    exercise['name'] = data.get('name', exercise['name'])
                    exercise['parameters'] = data.get('parameters', exercise['parameters'])
                    exercise['info'] = data.get('info', exercise.get('info', ''))
                    exercise['recommended_sets'] = data.get('recommended_sets', exercise.get('recommended_sets'))
                    exercise['recommended_reps'] = data.get('recommended_reps', exercise.get('recommended_reps'))
                    break
            break
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<user_profile>/profiles/<profile_id>/exercises/<exercise_id>', methods=['DELETE'])
def delete_workout_profile_exercise(user_profile, profile_id, exercise_id):
    """Usuwa ćwiczenie z profilu ćwiczeń"""
    ensure_gym_dir()
    user_file = os.path.join(GYM_DATA_DIR, f'{user_profile}.json')
    
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    for profile in user_data.get('profiles', []):
        if profile['id'] == profile_id:
            profile['exercises'] = [ex for ex in profile['exercises'] if ex['id'] != exercise_id]
            break
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<user_profile>/profiles/<profile_id>/exercises/reorder', methods=['PUT'])
def reorder_workout_profile_exercises(user_profile, profile_id):
    """Zmienia kolejność ćwiczeń"""
    ensure_gym_dir()
    data = request.json
    new_order = data.get('order', [])
    user_file = os.path.join(GYM_DATA_DIR, f'{user_profile}.json')
    
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    for profile in user_data.get('profiles', []):
        if profile['id'] == profile_id:
            exercises_dict = {ex['id']: ex for ex in profile['exercises']}
            profile['exercises'] = [exercises_dict[ex_id] for ex_id in new_order if ex_id in exercises_dict]
            break
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<profile>/exercises', methods=['GET'])
def get_profile_exercises(profile):
    """Zwraca ćwiczenia dla profilu"""
    ensure_gym_dir()
    profile_file = os.path.join(GYM_DATA_DIR, f'{profile}.json')
    
    if not os.path.exists(profile_file):
        # Stwórz pusty profil
        profile_data = {
            'name': profile,
            'exercises': []
        }
        with open(profile_file, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)
        return jsonify(profile_data)
    
    with open(profile_file, 'r', encoding='utf-8') as f:
        profile_data = json.load(f)
    
    return jsonify(profile_data)

@app.route('/api/gym/<profile>/exercises', methods=['POST'])
def add_profile_exercise(profile):
    """Dodaje ćwiczenie do profilu"""
    ensure_gym_dir()
    data = request.json
    profile_file = os.path.join(GYM_DATA_DIR, f'{profile}.json')
    
    # Wczytaj lub stwórz profil
    if os.path.exists(profile_file):
        with open(profile_file, 'r', encoding='utf-8') as f:
            profile_data = json.load(f)
    else:
        profile_data = {'name': profile, 'exercises': []}
    
    # Dodaj nowe ćwiczenie
    new_exercise = {
        'id': str(int(time.time() * 1000)),
        'name': data.get('name'),
        'parameters': data.get('parameters', []),
        'info': data.get('info', ''),
        'recommended_sets': data.get('recommended_sets'),
        'recommended_reps': data.get('recommended_reps')
    }
    
    profile_data['exercises'].append(new_exercise)
    
    with open(profile_file, 'w', encoding='utf-8') as f:
        json.dump(profile_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True, 'exercise': new_exercise})

@app.route('/api/gym/<profile>/exercises/<exercise_id>', methods=['PUT'])
def update_profile_exercise(profile, exercise_id):
    """Aktualizuje ćwiczenie w profilu"""
    ensure_gym_dir()
    data = request.json
    profile_file = os.path.join(GYM_DATA_DIR, f'{profile}.json')
    
    with open(profile_file, 'r', encoding='utf-8') as f:
        profile_data = json.load(f)
    
    for exercise in profile_data['exercises']:
        if exercise['id'] == exercise_id:
            exercise['name'] = data.get('name', exercise['name'])
            exercise['parameters'] = data.get('parameters', exercise['parameters'])
            exercise['info'] = data.get('info', exercise.get('info', ''))
            exercise['recommended_sets'] = data.get('recommended_sets', exercise.get('recommended_sets'))
            exercise['recommended_reps'] = data.get('recommended_reps', exercise.get('recommended_reps'))
            break
    
    with open(profile_file, 'w', encoding='utf-8') as f:
        json.dump(profile_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<profile>/exercises/<exercise_id>', methods=['DELETE'])
def delete_profile_exercise(profile, exercise_id):
    """Usuwa ćwiczenie z profilu"""
    ensure_gym_dir()
    profile_file = os.path.join(GYM_DATA_DIR, f'{profile}.json')
    
    with open(profile_file, 'r', encoding='utf-8') as f:
        profile_data = json.load(f)
    
    profile_data['exercises'] = [ex for ex in profile_data['exercises'] if ex['id'] != exercise_id]
    
    with open(profile_file, 'w', encoding='utf-8') as f:
        json.dump(profile_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<profile>/exercises/reorder', methods=['PUT'])
def reorder_profile_exercises(profile):
    """Zmienia kolejność ćwiczeń"""
    ensure_gym_dir()
    data = request.json
    new_order = data.get('order', [])
    profile_file = os.path.join(GYM_DATA_DIR, f'{profile}.json')
    
    with open(profile_file, 'r', encoding='utf-8') as f:
        profile_data = json.load(f)
    
    # Twórz nową listę w odpowiedniej kolejności
    exercises_dict = {ex['id']: ex for ex in profile_data['exercises']}
    profile_data['exercises'] = [exercises_dict[ex_id] for ex_id in new_order if ex_id in exercises_dict]
    
    with open(profile_file, 'w', encoding='utf-8') as f:
        json.dump(profile_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

@app.route('/api/gym/<user_profile>/profiles/<profile_id>/workouts', methods=['POST'])
def save_workout_profile_workout(user_profile, profile_id):
    """Zapisuje trening"""
    ensure_gym_dir()
    data = request.json
    
    workouts_file = os.path.join(GYM_DATA_DIR, f'{user_profile}_{profile_id}_workouts.json')
    
    if os.path.exists(workouts_file):
        with open(workouts_file, 'r', encoding='utf-8') as f:
            workouts = json.load(f)
    else:
        workouts = []
    
    # Dodaj ID i zapisz
    workout_id = str(int(time.time() * 1000))
    data['id'] = workout_id
    data['user_profile'] = user_profile
    data['workout_profile_id'] = profile_id
    
    workouts.append(data)
    
    with open(workouts_file, 'w', encoding='utf-8') as f:
        json.dump(workouts, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True, 'workout_id': workout_id})

@app.route('/api/gym/<user_profile>/profiles/<profile_id>/workouts', methods=['GET'])
def get_workout_profile_workouts(user_profile, profile_id):
    """Pobiera treningi"""
    ensure_gym_dir()
    workouts_file = os.path.join(GYM_DATA_DIR, f'{user_profile}_{profile_id}_workouts.json')
    
    if not os.path.exists(workouts_file):
        return jsonify([])
    
    with open(workouts_file, 'r', encoding='utf-8') as f:
        workouts = json.load(f)
    
    return jsonify(workouts)

@app.route('/api/gym/<user_profile>/profiles/<profile_id>/workouts/<workout_id>', methods=['DELETE'])
def delete_workout_profile_workout(user_profile, profile_id, workout_id):
    """Usuwa trening"""
    ensure_gym_dir()
    workouts_file = os.path.join(GYM_DATA_DIR, f'{user_profile}_{profile_id}_workouts.json')
    
    with open(workouts_file, 'r', encoding='utf-8') as f:
        workouts = json.load(f)
    
    workouts = [w for w in workouts if w.get('id') != workout_id]
    
    with open(workouts_file, 'w', encoding='utf-8') as f:
        json.dump(workouts, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

# Stare endpointy - zachowane dla kompatybilności
@app.route('/api/gym/<profile>/workouts', methods=['POST'])
def save_profile_workout(profile):
    """Zapisuje trening profilu"""
    ensure_gym_dir()
    data = request.json
    
    workouts_file = os.path.join(GYM_DATA_DIR, f'{profile}_workouts.json')
    
    if os.path.exists(workouts_file):
        with open(workouts_file, 'r', encoding='utf-8') as f:
            workouts = json.load(f)
    else:
        workouts = []
    
    # Dodaj ID i zapisz
    workout_id = str(int(time.time() * 1000))
    data['id'] = workout_id
    data['profile'] = profile
    
    workouts.append(data)
    
    with open(workouts_file, 'w', encoding='utf-8') as f:
        json.dump(workouts, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True, 'workout_id': workout_id})

@app.route('/api/gym/<profile>/workouts', methods=['GET'])
def get_profile_workouts(profile):
    """Pobiera treningi profilu"""
    ensure_gym_dir()
    workouts_file = os.path.join(GYM_DATA_DIR, f'{profile}_workouts.json')
    
    if not os.path.exists(workouts_file):
        return jsonify([])
    
    with open(workouts_file, 'r', encoding='utf-8') as f:
        workouts = json.load(f)
    
    return jsonify(workouts)

@app.route('/api/gym/<profile>/workouts/<workout_id>', methods=['DELETE'])
def delete_profile_workout(profile, workout_id):
    """Usuwa trening profilu"""
    ensure_gym_dir()
    workouts_file = os.path.join(GYM_DATA_DIR, f'{profile}_workouts.json')
    
    with open(workouts_file, 'r', encoding='utf-8') as f:
        workouts = json.load(f)
    
    workouts = [w for w in workouts if w.get('id') != workout_id]
    
    with open(workouts_file, 'w', encoding='utf-8') as f:
        json.dump(workouts, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True})

FEEDBACK_DIR = 'feedbacks'

FEEDBACK_DIR = 'feedbacks'  # Legacy, kept for reference

@app.route('/api/feedback', methods=['POST'])
def save_feedback():
    """Zapisuje feedback użytkownika do bazy danych"""
    data = request.json
    feedback_text = data.get('feedback')
    
    if not feedback_text:
        return jsonify({'success': False, 'error': 'No feedback text'})
    
    # Zapisz feedback do bazy danych
    feedback = Feedback(text=feedback_text)
    db.session.add(feedback)
    db.session.commit()
    
    timestamp = feedback.created_at.strftime('%Y%m%d_%H%M%S')
    filename = f'feedback_{timestamp}.txt'
    
    return jsonify({'success': True, 'filename': filename})

@app.route('/api/profiles', methods=['GET'])
def get_profiles():
    """Pobiera listę profili z bazy danych"""
    profiles = MealProfile.query.all()
    
    if not profiles:
        # Domyślny profil
        default_profile = MealProfile(name='Gość')
        db.session.add(default_profile)
        db.session.commit()
        return jsonify(['Gość'])
    
    return jsonify([p.name for p in profiles])

@app.route('/api/profiles', methods=['POST'])
def add_profile():
    """Dodaje nowy profil do bazy danych"""
    data = request.json
    profile_name = data.get('profile_name', '').strip()
    
    if not profile_name:
        return jsonify({'success': False, 'message': 'Nazwa profilu jest wymagana'})
    
    # Check if profile already exists
    existing_profile = MealProfile.query.filter_by(name=profile_name).first()
    if existing_profile:
        return jsonify({'success': False, 'message': 'Profil o tej nazwie już istnieje'})
    
    # Add new profile
    new_profile = MealProfile(name=profile_name)
    db.session.add(new_profile)
    db.session.commit()
    
    profiles = MealProfile.query.all()
    return jsonify({'success': True, 'profiles': [p.name for p in profiles]})

if __name__ == '__main__':
    print("🛒 Lista zakupów uruchomiona na http://localhost:2137")
    app.run(host='0.0.0.0', port=2137, debug=True)
