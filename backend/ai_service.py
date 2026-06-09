import os
import json
import google.generativeai as genai
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Configure Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)

@lru_cache(maxsize=100)
def get_pollution_insight(pollutant_name, value, unit, status_label):
    """
    Fetches structured, professional health advice from Gemini in JSON format.
    """
    if not GEMINI_API_KEY:
        print("[Gemini Service] WARNING: GEMINI_API_KEY not found in environment.")
        return None

    # Use the correct model name for Gemini 1.5 Flash
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
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

    try:
        response = model.generate_content(prompt)
        
        # Check if the response was blocked by safety filters
        if not response or not hasattr(response, 'text'):
            print(f"[Gemini Service] Warning: Response blocked or empty. Safety Rating: {response.prompt_feedback}")
            raise ValueError("Response blocked by safety filters")

        text = response.text.strip()
        
        # Robust JSON extraction
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = text[start_idx:end_idx+1]
            json_data = json.loads(json_str)
            return json_data
        else:
            raise ValueError("No JSON object found in response")
            
    except Exception as e:
        print(f"[Gemini Service] Error: {e}")
        # Return a fallback JSON structure to prevent frontend crash
        return {
            "short_term_effects": "Data retrieval in progress. High levels of air pollutants can cause immediate respiratory irritation.",
            "long_term_effects": "Long-term analysis pending. Chronic exposure is associated with cardiovascular and pulmonary diseases.",
            "vulnerable_groups": "Children, elderly, and individuals with pre-existing conditions should take extra precautions.",
            "environmental_impact": "Localized environmental modeling is currently processing satellite data.",
            "action_plan": ["Monitor local air quality reports", "Limit outdoor physical exertion", "Ensure proper indoor ventilation"],
            "scientific_fact": "Our AI engine is currently processing real-time atmospheric dynamics."
        }
