import json
from datetime import datetime, timedelta

# Wczytaj przepisy
with open('przepisy.json', 'r', encoding='utf-8') as f:
    recipes = json.load(f)

# Pogrupuj przepisy według dni
days_dict = {}
for recipe in recipes:
    day = recipe['day']
    if day not in days_dict:
        days_dict[day] = []
    days_dict[day].append(recipe)

# Sortuj dni chronologicznie
sorted_days = sorted(days_dict.keys(), key=lambda x: datetime.strptime(x.split()[1], '%d.%m.%Y'))

# Mapowanie dni tygodnia
weekdays = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']

# Utwórz nową listę z zduplikowanymi dniami
new_recipes = []
current_date = datetime.strptime('30.12.2025', '%d.%m.%Y')

# Dla każdego oryginalnego dnia, dodaj przepisy dwa razy
for i, day in enumerate(sorted_days):
    meals = days_dict[day]
    
    # Pierwsza i druga kopia dnia
    for copy in range(2):
        weekday_name = weekdays[current_date.weekday()]
        new_day_string = f"{weekday_name} {current_date.strftime('%d.%m.%Y')}"
        
        for meal in meals:
            new_meal = meal.copy()
            new_meal['day'] = new_day_string
            new_recipes.append(new_meal)
        
        current_date += timedelta(days=1)

# Zapisz nowy plik
with open('przepisy.json', 'w', encoding='utf-8') as f:
    json.dump(new_recipes, f, ensure_ascii=False, indent=2)

print(f"Zaktualizowano! Teraz jest {len(new_recipes)} posiłków od {new_recipes[0]['day']} do {new_recipes[-1]['day']}")
