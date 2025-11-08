from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os, json
import csv

# Load .env variables
load_dotenv()

app = Flask(__name__)

# Get your API key (or None)
api_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client if key exists
client = OpenAI(api_key=api_key) if api_key else None

# Load ingredients from CSV
ingredient_db = {}
with open("ingredients.csv", "r") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        ingredient = row['ingredient'].lower().strip()
        if ingredient not in ingredient_db:
            ingredient_db[ingredient] = {}
        ingredient_db[ingredient][row['concern']] = {
            "safe": row['safe'],
            "reason": row['reason']
        }

# --- Analyze function ---
def analyze_with_chatgpt(ingredient, concern):
    if client:  # Use real API
        prompt = f"""
        Analyze whether the ingredient '{ingredient}' is suitable for {concern} skin.
        Reply ONLY in JSON format:
        {{
          "ingredient": "{ingredient}",
          "safe": "safe" | "neutral" | "not safe",
          "reason": "short reason"
        }}
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        text = response.choices[0].message.content.strip()
        try:
            return json.loads(text)
        except:
            return {"ingredient": ingredient, "safe": "unknown", "reason": text}
    else:  # MOCK API (for testing without key)
        return {"ingredient": ingredient, "safe": "safe", "reason": "mocked result for testing"}

# --- Flask route ---
@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    ingredients = data.get("ingredients", [])
    concern = data.get("concern", "acne")

    results = []
    for ing in ingredients:
        ing_lower = ing.lower().strip()
        # Check database first
        if ing_lower in ingredient_db and concern in ingredient_db[ing_lower]:
            info = ingredient_db[ing_lower][concern]
            results.append({
                "ingredient": ing,
                "safe": info["safe"],
                "reason": info["reason"]
            })
        else:
            # Call API (or mock)
            ai_result = analyze_with_chatgpt(ing, concern)
            # Save to database
            if ing_lower not in ingredient_db:
                ingredient_db[ing_lower] = {}
            ingredient_db[ing_lower][concern] = {
                "safe": ai_result["safe"],
                "reason": ai_result["reason"]
            }
            results.append(ai_result)

    # Save back to CSV
    with open("ingredients.csv", "w", newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['ingredient', 'concern', 'safe', 'reason'])
        writer.writeheader()
        for ingredient, concerns in ingredient_db.items():
            for concern, info in concerns.items():
                writer.writerow({
                    'ingredient': ingredient,
                    'concern': concern,
                    'safe': info['safe'],
                    'reason': info['reason']
                })

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)

