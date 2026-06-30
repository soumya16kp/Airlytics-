import os
import json
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

@lru_cache(maxsize=100)
def get_pollution_insight(pollutant_name, value, unit, status_label, question=None):
    """
    Fetches structured, professional health advice from Gemini in JSON format,
    or a conversational response if a specific user question is asked.
    Uses the new google.genai SDK.
    """
    if not GEMINI_API_KEY:
        print("[Gemini Service] WARNING: GEMINI_API_KEY not found in environment.")
        return _fallback_insight() if not question else "API key missing. Cannot answer question."

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

        if question:
            prompt = f"""
You are a helpful Environmental Health Scientist.
The user is asking a question about the current air quality.

Current Status:
Pollutant: {pollutant_name}
Concentration: {value} {unit}
WHO Status: {status_label}

User Question: {question}

Provide a direct, concise, and scientifically accurate answer to the user's question.
Do not use markdown formatting. Do not return JSON. Just write the answer as a short paragraph.
"""
        else:
            prompt = f"""
You are a world-class Environmental Health Scientist.
Analyze the following air quality data and return a JSON object.

DATA:
Pollutant: {pollutant_name}
Exact Predicted ML Concentration: {value} {unit}
WHO Status: {status_label}

JSON Format Required:
{{
    "short_term_effects": "string (describe immediate response to {value} {unit})",
    "long_term_effects": "string (describe chronic risks of prolonged exposure to {value} {unit})",
    "vulnerable_groups": "string",
    "environmental_impact": "string",
    "action_plan": ["step 1", "step 2", "step 3"],
    "scientific_fact": "string"
}}

Rules:
- You MUST reference the exact value of {value} {unit} in your analysis.
- Be highly quantitative and scientific.
- Explain the exact harm this specific level causes.
- Return ONLY the JSON object. No extra text.
- Maximum 40 words per string field.
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )

        text = response.text.strip() if response and response.text else ''

        if question:
            return text

        # Robust JSON extraction
        start_idx = text.find('{')
        end_idx   = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str  = text[start_idx:end_idx + 1]
            json_data = json.loads(json_str)
            return json_data
        else:
            raise ValueError(f"No JSON object found in response: {text[:200]}")

    except Exception as e:
        print(f"[Gemini Service] Error: {e}")
        return _fallback_insight() if not question else "An error occurred while generating the answer. Please try again."


def _fallback_insight():
    """Returns a structured fallback when the AI service is unavailable."""
    return {
        "short_term_effects": "High pollutant levels can cause immediate respiratory irritation, coughing, and reduced lung function.",
        "long_term_effects": "Chronic exposure is associated with cardiovascular disease, reduced lung capacity, and increased cancer risk.",
        "vulnerable_groups": "Children, elderly, pregnant women, and individuals with asthma or pre-existing conditions face highest risk.",
        "environmental_impact": "Elevated levels contribute to smog formation, acid rain, and ecosystem degradation.",
        "action_plan": [
            "Limit outdoor physical activity during high-pollution periods",
            "Wear N95 or equivalent masks when outdoors",
            "Use air purifiers with HEPA filters indoors"
        ],
        "scientific_fact": "WHO guidelines set strict limits based on epidemiological studies showing dose-response relationships between pollutant exposure and health outcomes."
    }
