import os
import shutil
from huggingface_hub import login, upload_folder

# Find models
base_dir = r"c:\Users\DELL\.gemini\antigravity\scratch\Airlytics"
upload_dir = os.path.join(base_dir, "hf_upload_temp")
os.makedirs(upload_dir, exist_ok=True)

models = [
    r"backend\models\no2_optimized.cbm",
    r"backend\models\co_prediction_model.pkl",
    r"backend\models\o3_model_new.pkl",
    r"backend\models\PM25_Complete_Model.pkl",
]

print("Gathering models into temporary folder...")
for m in models:
    src = os.path.join(base_dir, m)
    if os.path.exists(src):
        print(f"Copying {os.path.basename(src)}...")
        shutil.copy(src, upload_dir)
    else:
        print(f"NOT FOUND: {src}")

print("\n--- Logging in to Hugging Face ---")
# This will prompt you for your token in the terminal
login()

print("\n--- Uploading models ---")
upload_folder(
    folder_path=upload_dir, 
    repo_id="ObitUchiha91/airlytics-models", 
    repo_type="model"
)
print("\nDone! Upload complete.")
