import os
import json
import time
import random
import requests
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
# Get your FREE API keys from: https://console.groq.com/keys
# Extract all keys that start with GROQ_API_KEY from .env
GROQ_KEYS = [v for k, v in os.environ.items() if k.startswith("GROQ_API_KEY") and v]
if not GROQ_KEYS:
    print("❌ No GROQ_API_KEY found in .env")
    exit(1)

current_key_idx = 0
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Using Llama 3.3 70B - Very smart, very fast, runs on Groq's cloud (No heat on Mac!)
MODEL_NAME = "llama-3.3-70b-versatile" 

# ─── Firebase ─────────────────────────────────────────────────────────────────
db = None
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase connected! Questions will be saved to App Database.", flush=True)
    except Exception as e:
        print(f"⚠️ No DB connection. Saving only locally. Error: {e}", flush=True)
except Exception as e:
    print(f"⚠️ No Firebase module. Saving only locally. Error: {e}", flush=True)

NTA_SYLLABUS = {
    "Physics": ["Kinematics", "Laws of Motion", "Rotational Motion", "Thermodynamics", "Electrostatics", "Magnetism", "Optics"],
    "Chemistry": ["Atomic Structure", "Equilibrium", "Redox Reactions", "Organic Chemistry Basics", "Hydrocarbons", "Coordination Compounds"],
    "Maths": ["Complex Numbers", "Matrices", "Calculus", "Probability", "3D Geometry", "Vectors"]
}

DATASET_FILE = "jee_custom_dataset.jsonl"

def append_to_dataset(q_data):
    with open(DATASET_FILE, "a") as f:
        training_row = {
            "instruction": f"Solve this JEE {q_data['subject']} question and explain step-by-step.",
            "input": f"Question: {q_data['question']}\nOptions: {q_data['options']}",
            "output": f"Correct Answer: {q_data['correctAnswer']}\nExplanation: {q_data['explanation']}"
        }
        f.write(json.dumps(training_row) + "\n")

def generate_from_groq(subject, topic):
    global current_key_idx
    print(f"\n☁️ Generating 1 {subject} ({topic}) question via Groq Cloud...", flush=True)
    
    prompt = f"""You are an elite IIT JEE question setter strictly following the LATEST NTA REVISED SYLLABUS (2024-2025).
Generate exactly ONE extremely hard, conceptual multiple-choice question for {subject} on the topic '{topic}'.
CRITICAL RULES:
1. DO NOT include any topics that were recently deleted by NTA (e.g., Solid State, Polymer, S-Block, Communication Systems, Mathematical Reasoning, etc.).
2. Focus on recent trends: Assertion-Reasoning, Statement-based, or multi-concept numericals.
3. Output ONLY a raw JSON object with these exact keys:
"question" (string), "options" (array of 4 strings), "answer_index" (integer 0-3), "hint" (string), "explanation" (detailed step-by-step string)."""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a JSON generating API. Always return a valid JSON object."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }

    # Try each key once before failing completely
    for _ in range(len(GROQ_KEYS)):
        current_key = GROQ_KEYS[current_key_idx]
        headers = {
            "Authorization": f"Bearer {current_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            
            # If rate limited (429), switch to the next key
            if response.status_code == 429:
                print(f"⚠️ Rate limit hit on Key {current_key_idx + 1}. Switching to next key...")
                current_key_idx = (current_key_idx + 1) % len(GROQ_KEYS)
                continue
                
            if not response.ok:
                print(f"❌ Groq API Error: {response.text}")
                response.raise_for_status()
                
            raw_text = response.json()["choices"][0]["message"]["content"]
            break # Success, exit retry loop
            
        except Exception as e:
            print(f"❌ Network or API Error: {e}", flush=True)
            return 0
    else:
        # If loop finishes without breaking, all keys are rate-limited
        print("❌ All API keys are rate-limited. Please wait 24 hours or add more keys.")
        return -1 # Special return code to stop the script
        
    try:
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
            "source": f"groq_{MODEL_NAME}"
        }
        
        append_to_dataset(formatted_q)
        
        # Save to Firebase too!
        if db:
            from firebase_admin import firestore as fs
            col = db.collection("questions").document()
            formatted_q["id"] = col.id
            formatted_q["createdAt"] = fs.SERVER_TIMESTAMP
            col.set(formatted_q)
            
        print("✅ Question generated and saved to Local Dataset & Firebase!", flush=True)
        return 1
    except Exception as e:
        print(f"❌ Failed to parse JSON: {e}", flush=True)
        return 0

def run_cloud_generator(target=1000):
    print(f"🚀 Starting Cloud Generator with {len(GROQ_KEYS)} API Keys for {target} questions.", flush=True)
    generated = 0
    subjects = list(NTA_SYLLABUS.keys())
    
    while generated < target:
        subject = random.choice(subjects)
        topic = random.choice(NTA_SYLLABUS[subject])
        
        success = generate_from_groq(subject, topic)
        if success == 1:
            generated += 1
            print(f"Progress: {generated}/{target}", flush=True)
        elif success == -1:
            # All keys are exhausted
            print("🛑 Stopping generator because all keys are out of limit.")
            break
        
        # Groq has a rate limit of 30 requests per minute on free tier. 
        # Sleeping for 2.5 seconds keeps us perfectly under the limit!
        time.sleep(2.5)

if __name__ == "__main__":
    run_cloud_generator(1000)
