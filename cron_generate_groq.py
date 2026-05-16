import os
import json
import time
import random
import requests
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
# Get your FREE API key from: https://console.groq.com/keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
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
    print(f"\n☁️ Generating 1 {subject} ({topic}) question via Groq Cloud...", flush=True)
    
    prompt = f"""You are an IIT JEE Advanced expert. 
Generate exactly ONE extremely hard multiple-choice question for {subject} on '{topic}'.
Output ONLY a raw JSON object with these exact keys:
"question" (string), "options" (array of 4 strings), "answer_index" (integer 0-3), "hint" (string), "explanation" (detailed step-by-step string)."""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a JSON generating API. Always return a valid JSON object."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        if not response.ok:
            print(f"❌ Groq API Error: {response.text}")
        response.raise_for_status()
        raw_text = response.json()["choices"][0]["message"]["content"]
        
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
        print(f"❌ Failed to generate/parse: {e}", flush=True)
        return 0

def run_cloud_generator(target=1000):
    if not GROQ_API_KEY:
        print("❌ Please add GROQ_API_KEY to your backend/.env file first!", flush=True)
        print("Get it for free at: https://console.groq.com/keys", flush=True)
        return

    print(f"🚀 Starting Cloud Generation for {target} questions. Your Mac M2 will stay perfectly cool! ❄️", flush=True)
    generated = 0
    subjects = list(NTA_SYLLABUS.keys())
    
    while generated < target:
        subject = random.choice(subjects)
        topic = random.choice(NTA_SYLLABUS[subject])
        
        success = generate_from_groq(subject, topic)
        if success:
            generated += 1
            print(f"Progress: {generated}/{target}", flush=True)
        
        # Groq has a rate limit of 30 requests per minute on free tier. 
        # Sleeping for 2.5 seconds keeps us perfectly under the limit!
        time.sleep(2.5)

if __name__ == "__main__":
    run_cloud_generator(1000)
