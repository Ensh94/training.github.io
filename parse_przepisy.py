import json
import re

def parse_przepisy():
    with open('przepisy_extracted.txt', 'r', encoding='cp1250') as f:
        content = f.read()
    
    przepisy = []
    
    # Dzielimy na poszczególne dni
    days = re.split(r'((?:Wtorek|îroda|Czwartek|Pi╣tek|Sobota|Niedziela)\s+\d{2}\.\d{2}\.\d{4})', content)
    
    current_day = None
    for i in range(1, len(days), 2):
        if i+1 < len(days):
            day_name = days[i].strip()
            day_content = days[i+1]
            
            # Wyciągamy poszczególne posiłki
            meals = re.split(r'\n(îniadanie|Drugie ťniadanie|Obiad|Podwieczorek|Kolacja)\s*\(', day_content)
            
            for j in range(1, len(meals), 2):
                if j+1 < len(meals):
                    meal_type = meals[j].strip()
                    meal_content = meals[j+1]
                    
                    # Wyciągamy informacje o kalorach
                    kcal_match = re.search(r'(\d+)\s*kcal', meal_content)
                    kcal = kcal_match.group(1) if kcal_match else '0'
                    
                    # Wyciągamy nazwę przepisu (pierwsza linia po białku/tłuszczach/węglowodanach)
                    lines = meal_content.split('\n')
                    recipe_name = None
                    ingredients = []
                    instructions = []
                    
                    in_ingredients = True
                    for line in lines[1:]:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # Pierwsza niepusta linia po makroskładnikach to nazwa
                        if not recipe_name and not re.match(r'bia│ko|t│uszcze|wŕglowodany|\d+ min', line):
                            recipe_name = line
                            continue
                        
                        # Jeśli linia zaczyna się wielką literą i jest długa, to instrukcja
                        if recipe_name and len(line) > 50 and line[0].isupper():
                            in_ingredients = False
                            instructions.append(line)
                        # Jeśli zawiera ilości, to składnik
                        elif recipe_name and re.search(r'\d+\s*(g|ml|sztuk|│y┐|garť|szklank|plastry|kawa│|opakowa)', line):
                            if in_ingredients:
                                ingredients.append(line)
                    
                    if recipe_name:
                        przepisy.append({
                            'day': day_name,
                            'meal_type': meal_type,
                            'name': recipe_name,
                            'kcal': kcal,
                            'ingredients': ingredients,
                            'instructions': ' '.join(instructions)
                        })
    
    with open('przepisy.json', 'w', encoding='utf-8') as f:
        json.dump(przepisy, f, ensure_ascii=False, indent=2)
    
    print(f"Zapisano {len(przepisy)} przepisów")

if __name__ == '__main__':
    parse_przepisy()
