import os
import json
import time
import random
import requests

# ─── Config ───────────────────────────────────────────────────────────────────
# Ensure Ollama is running locally (e.g., 'ollama run llama3' or 'ollama run mistral')
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3" # You can change this to 'mistral' or 'phi3' if you have them

NTA_SYLLABUS = {
    "Physics": ["Kinematics", "Laws of Motion", "Rotational Motion", "Thermodynamics", "Electrostatics", "Magnetism", "Optics"],
    "Chemistry": ["Atomic Structure", "Equilibrium", "Redox Reactions", "Organic Chemistry Basics", "Hydrocarbons", "Coordination Compounds"],
    "Maths": ["Complex Numbers", "Matrices", "Calculus", "Probability", "3D Geometry", "Vectors"]
}

# ─── Firestore (Optional) ─────────────────────────────────────────────────────
db = None
try:
    import firebase_admin
    from firebase_admin import firestore
    try:
        db = firestore.client()
        print("✅ Firestore connected. Questions will be saved to DB.")
    except:
        print("⚠️ Saving to local JSON file instead of Firestore.")
except:
    print("⚠️ Saving to local JSON file instead of Firestore.")

# ─── Local JSON Backup ────────────────────────────────────────────────────────
DATASET_FILE = "jee_custom_dataset.jsonl"

def append_to_dataset(q_data):
    """Saves data in JSONL format, perfect for fine-tuning your custom LLM later."""
    with open(DATASET_FILE, "a") as f:
        # Formatting perfectly for future instruction-tuning
        training_row = {
            "instruction": f"Solve this JEE {q_data['subject']} question and explain step-by-step.",
            "input": f"Question: {q_data['question']}\nOptions: {q_data['options']}",
            "output": f"Correct Answer: {q_data['correctAnswer']}\nExplanation: {q_data['explanation']}"
        }
        f.write(json.dumps(training_row) + "\n")

# ─── Generator ────────────────────────────────────────────────────────────────
def generate_from_ollama(subject, topic):
    print(f"\n🧠 Generating 1 {subject} ({topic}) question using local {MODEL_NAME}...")
    
    prompt = f"""You are an IIT JEE Advanced expert. 
Generate exactly ONE extremely hard multiple-choice question for {subject} on '{topic}'.
Do not output any introductory text. Output ONLY a raw JSON object with these exact keys:
"question" (string), "options" (array of 4 strings), "answer_index" (integer 0-3), "hint" (string), "explanation" (detailed step-by-step string)."""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json" # Forces Ollama to return valid JSON!
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        response.raise_for_status()
        raw_text = response.json().get("response", "")
        
        q = json.loads(raw_text)
        opts = q["options"]
        ai = int(q["answer_index"])
        
        formatted_q = {
            "subject": subject,
            "topic": topic,
            "question": q["question"],
            "options": opts,
            "answer_index": ai,
            "correctAnswer": opts[ai],
            "hint": q.get("hint", ""),
            "explanation": q.get("explanation", ""),
            "source": f"local_{MODEL_NAME}"
        }
        
        # Save to local fine-tuning dataset
        append_to_dataset(formatted_q)
        
        # Save to Firestore (App Database)
        if db:
            col = db.collection("questions").document()
            formatted_q["id"] = col.id
            col.set(formatted_q)
            
        print("✅ Question generated and saved successfully!")
        return 1
    except Exception as e:
        print(f"❌ Failed to generate/parse: {e}")
        return 0

def run_local_generator(target=1000):
    print(f"🚀 Starting Local Free Generation for {target} questions!")
    generated = 0
    subjects = list(NTA_SYLLABUS.keys())
    
    while generated < target:
        subject = random.choice(subjects)
        topic = random.choice(NTA_SYLLABUS[subject])
        
        success = generate_from_ollama(subject, topic)
        if success:
            generated += 1
            print(f"Progress: {generated}/{target}")
        
        # No API limit sleeps needed! Your computer runs as fast as it can.

if __name__ == "__main__":
    run_local_generator(1000)
