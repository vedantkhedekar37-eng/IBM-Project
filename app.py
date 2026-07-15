"""
╔══════════════════════════════════════════════════════════════════╗
║              ArogyaAi — IBM Watsonx.ai Nutrition Chatbot         ║
║              Backend: Flask + ibm-watsonx-ai SDK                 ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import math
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

# ─────────────────────────────────────────────────────────────────
# AGENT INSTRUCTIONS  — Customize ArogyaAi's behavior here
# ─────────────────────────────────────────────────────────────────
AGENT_INSTRUCTIONS = """
You are ArogyaAi, a compassionate and knowledgeable AI nutrition assistant
specialized in Indian dietary habits, Ayurvedic wellness, and modern
evidence-based nutrition science.

SCOPE — STRICT RULE (HIGHEST PRIORITY):
- You ONLY answer questions related to health, nutrition, diet, fitness,
  wellness, Ayurveda, medical symptoms (general), and food.
- If the user asks about ANYTHING outside this scope — such as coding,
  politics, entertainment, sports, finance, history, geography, relationships,
  jokes, or general knowledge — politely decline and redirect them.
- When declining, respond with exactly this format:
  "I'm ArogyaAi, your health and nutrition assistant. I can only help with
  health, diet, and wellness topics. Please ask me something related to
  nutrition, fitness, or well-being! 🌿"
- Do NOT attempt to answer even partially if the question is off-topic.

PERSONA & TONE:
- Warm, encouraging, and culturally sensitive
- Speak in simple English; use Hindi terms (dal, roti, sabzi, ghee, etc.)
  where it feels natural
- Address users respectfully; use "aap" references lightly for warmth
- Never be dismissive; always validate the user's effort

SPECIALIZATIONS:
- Indian regional cuisines (North, South, East, West, Northeast)
- Vegetarian, vegan, Jain, and sattvic diets
- Diabetic-friendly, PCOS, thyroid, and heart-healthy meal plans
- Ayurvedic doshas (Vata, Pitta, Kapha) and seasonal eating
- Calorie counting for Indian dishes (dal makhani, biryani, idli, etc.)
- Budget-friendly nutrition for Indian households
- Festive / fasting diet guidance (Navratri, Ekadashi, Ramadan, etc.)

NUTRITION GUIDELINES:
- Base recommendations on ICMR-NIN (Indian Council of Medical Research)
  Dietary Reference Values
- Refer to Indian food composition tables for accurate calorie data
- Promote whole grains (millets, jowar, bajra) over refined carbs
- Encourage traditional superfoods: turmeric, amla, moringa, ashwagandha
- Suggest protein-rich vegetarian combos (dal+rice, rajma+roti, etc.)

FAMILY PROFILE HANDLING:
- When multiple family members are provided, tailor advice per member
- Consider age groups: infant, child, teenager, adult, senior
- Flag special conditions (diabetes, hypertension, pregnancy, lactation)
- Suggest unified family meals with small per-person modifications

MEAL PLANNING FORMAT:
- Always provide: Breakfast | Mid-morning snack | Lunch | Evening snack | Dinner
- Include approximate calories and macros per meal
- Suggest a weekly rotation to avoid monotony
- Add a hydration reminder (minimum 8 glasses / 2 litres water)

SAFETY RULES (MUST FOLLOW):
- NEVER diagnose medical conditions or prescribe medication
- Always advise consulting a registered dietitian or doctor for medical issues
- Do NOT recommend extreme calorie restriction (below 1200 kcal for women,
  1500 kcal for men) without medical supervision
- Flag potential allergens (nuts, dairy, gluten) clearly
- Avoid making absolute claims; use "research suggests" / "generally recommended"

RESPONSE STYLE:
- Use bullet points and emoji sparingly (🥗 🌿 💪) for readability
- For meal plans, use a clean table or structured list
- Keep responses concise (under 400 words) unless a detailed plan is requested
- End every response with one motivational health tip or quote
"""
# ─────────────────────────────────────────────────────────────────

# Load .env relative to THIS file's directory, not the process cwd.
# This ensures credentials are found whether Flask is started from
# ArogyaAi/ or from the workspace root (d:\Project).
_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(_HERE, ".env"))

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "arogya-secret-2024")

# ── IBM Watsonx.ai configuration ──────────────────────────────────
# Read directly from os.environ (populated by load_dotenv above).
# mistral-small is a full instruct model with far lower free-tier contention
# than the 70B llama. Change MODEL_ID in .env to override at any time.
MODEL_ID = os.getenv("MODEL_ID", "mistralai/mistral-small-3-1-24b-instruct-2503")

# Startup validation — fail fast with a clear message if keys are missing.
def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"[ArogyaAi] Required environment variable '{name}' is missing or empty.\n"
            f"  → Copy .env.example to .env and fill in your IBM Cloud credentials."
        )
    return value

# Lazy-init model client
_model: ModelInference | None = None

def get_model() -> ModelInference:
    """Return a cached ModelInference instance, creating it on first call."""
    global _model
    if _model is None:
        api_key    = _require_env("IBM_API_KEY")
        project_id = _require_env("IBM_PROJECT_ID")
        url        = os.getenv("IBM_URL", "https://us-south.ml.cloud.ibm.com")

        credentials = Credentials(api_key=api_key, url=url)
        client      = APIClient(credentials)
        _model = ModelInference(
            model_id=MODEL_ID,
            api_client=client,
            project_id=project_id,
            params={
                GenParams.MAX_NEW_TOKENS: 900,
                GenParams.MIN_NEW_TOKENS: 30,
                GenParams.TEMPERATURE: 0.7,
                GenParams.TOP_P: 0.9,
                GenParams.REPETITION_PENALTY: 1.1,
            },
        )
    return _model


def generate_with_retry(prompt: str, max_retries: int = 4) -> str:
    """Call model.generate_text with exponential backoff on 429 rate-limit errors.
    Waits 5 s → 10 s → 20 s → 40 s before giving up."""
    delay = 5
    for attempt in range(max_retries):
        try:
            return get_model().generate_text(prompt=prompt)
        except Exception as exc:
            msg = str(exc)
            is_rate_limit = "429" in msg or "consumption_limit_reached" in msg
            if is_rate_limit and attempt < max_retries - 1:
                app.logger.warning(
                    "Rate limit hit (attempt %d/%d). Retrying in %ds…",
                    attempt + 1, max_retries, delay,
                )
                time.sleep(delay)
                delay *= 2        # exponential backoff: 5 → 10 → 20 → 40
            else:
                if is_rate_limit:
                    raise RuntimeError(
                        "The IBM Watsonx free plan is currently busy. "
                        "Please wait 30 seconds and try again."
                    )
                raise


def build_prompt(user_message: str, history: list, family_profiles: list) -> str:
    """Construct a prompt using the Granite 3.x / Llama-3 instruct chat template:
      <|system|>…<|user|>…<|assistant|>…
    This format is required for ibm/granite-3-1-8b-base and all modern
    Granite/Llama instruct models on Watsonx.ai."""

    # Build optional family context block appended to the system prompt
    family_block = ""
    if family_profiles:
        family_block = "\n\nFAMILY PROFILES:\n"
        for m in family_profiles:
            family_block += (
                f"- {m.get('name','Member')} | Age: {m.get('age','?')} | "
                f"Gender: {m.get('gender','?')} | Goal: {m.get('goal','General health')} | "
                f"Conditions: {m.get('conditions','None')}\n"
            )

    system_block = f"<|system|>\n{AGENT_INSTRUCTIONS.strip()}{family_block}\n"

    # Replay last 6 turns using the instruct template
    history_block = ""
    for turn in history[-6:]:
        if turn["role"] == "user":
            history_block += f"<|user|>\n{turn['content']}\n"
        else:
            history_block += f"<|assistant|>\n{turn['content']}\n"

    prompt = (
        f"{system_block}"
        f"{history_block}"
        f"<|user|>\n{user_message}\n"
        f"<|assistant|>\n"
    )
    return prompt


# ── Routes ────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main SPA."""
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat messages."""
    data            = request.get_json(force=True)
    user_message    = data.get("message", "").strip()
    history         = data.get("history", [])
    family_profiles = data.get("familyProfiles", [])

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    try:
        prompt = build_prompt(user_message, history, family_profiles)
        result = generate_with_retry(prompt=prompt)
        reply  = result.strip() if isinstance(result, str) else result
        return jsonify({"reply": reply, "timestamp": datetime.now().isoformat()})
    except Exception as exc:
        app.logger.error("Watsonx error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/bmi", methods=["POST"])
def calculate_bmi():
    """Calculate BMI and return category + recommendation."""
    data   = request.get_json(force=True)
    try:
        weight = float(data["weight"])   # kg
        height = float(data["height"])   # cm
    except (KeyError, ValueError):
        return jsonify({"error": "Provide weight (kg) and height (cm)"}), 400

    height_m = height / 100
    bmi      = round(weight / (height_m ** 2), 1)

    if bmi < 18.5:
        category, color, advice = "Underweight", "#f59e0b", (
            "Focus on calorie-dense, nutrient-rich foods like nuts, ghee, "
            "full-fat dairy, and whole grains. Aim for 3 main meals + 3 snacks."
        )
    elif bmi < 23:
        category, color, advice = "Normal weight", "#22c55e", (
            "Great! Maintain your weight with a balanced Indian thali — "
            "dal, sabzi, roti/rice, curd, and seasonal fruits."
        )
    elif bmi < 27.5:
        category, color, advice = "Overweight", "#f97316", (
            "Reduce refined carbs and sugar. Increase fibre (oats, daliya, "
            "vegetables) and include 30 min brisk walk daily."
        )
    else:
        category, color, advice = "Obese", "#ef4444", (
            "Please consult a doctor or registered dietitian. Focus on "
            "portion control, low-GI foods, and regular physical activity."
        )

    # Healthy weight range for reference
    min_healthy = round(18.5 * (height_m ** 2), 1)
    max_healthy = round(22.9 * (height_m ** 2), 1)

    return jsonify({
        "bmi": bmi,
        "category": category,
        "color": color,
        "advice": advice,
        "healthyRange": f"{min_healthy} – {max_healthy} kg",
    })


@app.route("/api/calories", methods=["POST"])
def calorie_needs():
    """Harris-Benedict TDEE calculator."""
    data = request.get_json(force=True)
    try:
        age      = int(data["age"])
        weight   = float(data["weight"])
        height   = float(data["height"])
        gender   = data["gender"].lower()
        activity = data.get("activity", "moderate")
        goal     = data.get("goal", "maintain")
    except (KeyError, ValueError):
        return jsonify({"error": "Provide age, weight, height, gender"}), 400

    # Mifflin-St Jeor BMR
    if gender == "female":
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5

    multipliers = {
        "sedentary": 1.2, "light": 1.375, "moderate": 1.55,
        "active": 1.725, "very_active": 1.9,
    }
    tdee = round(bmr * multipliers.get(activity, 1.55))

    goal_calories = {
        "lose":     tdee - 500,
        "maintain": tdee,
        "gain":     tdee + 400,
    }
    target = goal_calories.get(goal, tdee)

    return jsonify({
        "bmr": round(bmr),
        "tdee": tdee,
        "targetCalories": target,
        "protein_g":  round(weight * 1.2),
        "carbs_g":    round(target * 0.50 / 4),
        "fat_g":      round(target * 0.25 / 9),
    })


@app.route("/api/meal-plan", methods=["POST"])
def generate_meal_plan():
    """Use Watsonx to generate a 7-day Indian meal plan."""
    data = request.get_json(force=True)
    prefs = data.get("preferences", {})

    prompt_text = (
        f"<|system|>\n{AGENT_INSTRUCTIONS.strip()}\n"
        f"<|user|>\n"
        f"Generate a detailed 7-day Indian meal plan for the following profile:\n"
        f"- Calories target: {prefs.get('calories', 2000)} kcal/day\n"
        f"- Diet type: {prefs.get('dietType', 'Vegetarian')}\n"
        f"- Goal: {prefs.get('goal', 'Maintain weight')}\n"
        f"- Allergies/Avoid: {prefs.get('avoid', 'None')}\n"
        f"- Region preference: {prefs.get('region', 'North Indian')}\n"
        f"Format each day as: Day X | Breakfast | Lunch | Dinner | Snacks | Approx kcal\n"
        f"<|assistant|>\n"
    )

    try:
        result = generate_with_retry(prompt=prompt_text)
        return jsonify({"plan": result.strip()})
    except Exception as exc:
        app.logger.error("Meal plan error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/analyze-food", methods=["POST"])
def analyze_food():
    """Analyze a food item or meal description for nutrition info."""
    data      = request.get_json(force=True)
    food_item = data.get("food", "").strip()

    if not food_item:
        return jsonify({"error": "Provide a food item"}), 400

    prompt_text = (
        f"<|system|>\n{AGENT_INSTRUCTIONS.strip()}\n"
        f"<|user|>\n"
        f"Analyze the nutritional content of: {food_item}\n"
        f"Provide: calories, protein, carbs, fat, fibre, key vitamins/minerals, "
        f"health benefits, and any cautions. Use Indian standard serving sizes.\n"
        f"<|assistant|>\n"
    )

    try:
        result = generate_with_retry(prompt=prompt_text)
        return jsonify({"analysis": result.strip()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/health")
def health_check():
    return jsonify({
        "status": "ok",
        "model": MODEL_ID,
        "timestamp": datetime.now().isoformat(),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
