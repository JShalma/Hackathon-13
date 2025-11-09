import os
from dotenv import load_dotenv 
from flask import Flask, request, render_template
import json
from openai import OpenAI  

# Load environment variables from .env file immediately
load_dotenv() 

app = Flask(__name__)

# Paths to your JSON file
DATABASE_FILE = "data.json"


openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")

if not openrouter_api_key:
    # This prevents the app from running without a key
    raise ValueError("OPENROUTER_API_KEY environment variable not set. Please check your .env file and ensure python-dotenv is installed.")

# 2. Configure the client to use the OpenRouter endpoint
client = OpenAI(
    api_key=openrouter_api_key, 
    base_url="https://openrouter.ai/api/v1"  
)
# ----------------------------------------------------


# --- Helper Functions ---

def read_json(file_path):
    """Reads the local JSON database."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def write_json(file_path, data):
    """Writes to the local JSON database."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def lookup_chemical(name, chemicals_db):
    """Return chemical info if it exists in the database. Uses strip() for robustness."""
    clean_name = name.lower().strip()
    
    for chem in chemicals_db:
        db_chemical_name = chem.get("Chemical", "").lower().strip()
        
        if db_chemical_name == clean_name:
            return chem
    return None

def analyze_concerns(chemical_info, user_concerns):
    """Checks the chemical against user concerns and adds a 'Concern_Note' field."""
    notes = []
    
    # Check for Acne-prone
    if "acne" in user_concerns:
        try:
            # Safely check Acneogenic score, converting to float for comparison
            acne_risk = float(chemical_info.get("Acneogenic", 0))
        except (ValueError, TypeError):
            acne_risk = 0
            
        if acne_risk > 0:
            notes.append(f"⚠️ **Acne Alert:** May clog pores (Acneogenic score: {acne_risk}).")

    # Check for Sensitive Skin
    if "sensitive_skin" in user_concerns:
        sensitivity = chemical_info.get("Sensitivity_Risk", "Low").lower()
        if sensitivity == "medium":
            notes.append("❗️ **Sensitivity Warning:** Has a Medium risk of causing irritation.")
        elif sensitivity == "high":
            notes.append("❌ **High Irritant:** High risk for sensitive skin.")

    # Check for Fragrance-sensitive
    if "fragrance_free" in user_concerns:
        is_fragrance = chemical_info.get("Fragrance", "No").lower()
        if is_fragrance != "no":
            notes.append("👃 **Fragrance:** Contains fragrance or has a slight odor.")

    # Check for Environmental Impact
    if "eco" in user_concerns:
        eco = chemical_info.get("EnvironmentalImpact", "Unknown").lower()
        if "slow biodegradation" in eco or "toxic" in eco:
            notes.append("🌍 **Eco Concern:** Potential concern for slow breakdown or aquatic toxicity.")

    # Check for Anti-Aging/Hyperpigmentation benefits
    if "anti_aging" in user_concerns and chemical_info.get("Anti_Aging_Benefit") == "Yes":
        notes.append("✅ **Benefit:** Supports anti-aging goals.")
    
    if "hyperpigmentation" in user_concerns and chemical_info.get("Hyperpigmentation_Benefit") == "Yes":
        notes.append("✅ **Benefit:** Beneficial for targeting hyperpigmentation.")

    chemical_info["Concern_Note"] = notes
    return chemical_info

def add_chemical_gemini(name):
    """Fetch chemical info using Gemini via OpenRouter and add to JSON database."""
    try:
        chemicals_db = read_json(DATABASE_FILE)
        
        # System prompt for Gemini remains consistent with required JSON structure
        messages = [
            {"role": "system", "content": "You are an expert cosmetic chemist AI. Your ONLY output is a valid JSON object describing the chemical. The keys must include: Chemical, Description, Source, HumanHealth, EnvironmentalImpact, PregnancySafe, Fragrance, Acneogenic (0 or 1), Sensitivity_Risk (Low, Medium, or High), Hyperpigmentation_Benefit (Yes or No), and Anti_Aging_Benefit (Yes or No)."},
            {"role": "user", "content": f"Provide the analysis for the ingredient '{name}'."}
        ]
        
        response = client.chat.completions.create(
            # 💡 Model set for the lowest-cost option on OpenRouter
            model="google/gemini-2.5-flash-lite", 
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"} 
        )
        
        text = response.choices[0].message.content
        text = text.strip().replace('```json', '').replace('```', '')
        chem_data = json.loads(text)
        
        # Save to local database
        chemicals_db.append(chem_data)
        write_json(DATABASE_FILE, chemicals_db)
        return chem_data
    except Exception as e:
        print("API error:", e)
        # Fallback structure
        return {
            "Chemical": name,
            "Description": f"Analysis unavailable: API Key/Network Error. Details: {str(e)[:100]}",
            "Source": "API Error",
            "HumanHealth": "Unknown",
            "EnvironmentalImpact": "Unknown",
            "PregnancySafe": "Unknown",
            "Fragrance": "Unknown",
            "Acneogenic": 0, "Sensitivity_Risk": "Low", "Hyperpigmentation_Benefit": "No", "Anti_Aging_Benefit": "No"
        }

def get_chemicals(ingredient_list, user_concerns):
    """Return info for all ingredients, analyzing concerns after lookup/API call."""
    chemicals_db = read_json(DATABASE_FILE)
    results = []
    for ing in ingredient_list:
        cleaned_ing = ing.strip()
        if not cleaned_ing: continue # Skip empty strings
        
        chem_info = lookup_chemical(cleaned_ing, chemicals_db)
        if not chem_info:
            chem_info = add_chemical_gemini(cleaned_ing)
        
        # Analyze concerns here before adding to results
        chem_info = analyze_concerns(chem_info, user_concerns)
        results.append(chem_info)
    return results


# --- Flask Route ---

@app.route("/", methods=["GET", "POST"])
def index():
    chemicals_info = None
    product_name = None
    concerns = []

    if request.method == "POST":
        # 1. Collect form data
        inputs = request.form.getlist("ingredients")
        pasted_text = request.form.get("ingredients_text")
        product_name = request.form.get("product_name")
        concerns = request.form.getlist("concerns") # Capture concerns

        if pasted_text:
            # Handle various delimiters (comma, newline, semicolon) for pasted text
            pasted_ingredients = [i.strip() for i in pasted_text.replace('\n', ',').replace(';', ',').split(",") if i.strip()]
            inputs.extend(pasted_ingredients)
        
        inputs = [i for i in inputs if i] # Final cleanup for empty strings
        
        # 2. Get chemical info (pass concerns to the analysis function)
        if inputs:
            chemicals_info = get_chemicals(inputs, concerns)

    # Render the single index.html template
    return render_template("index.html", 
                           chemicals=chemicals_info, 
                           product_name=product_name,
                           concerns=concerns)

if __name__ == "__main__":
    app.run(debug=True)