import os
import sys
import json
import time
import random
import requests
import logging
from typing import List, Dict, Any

# Adjust path so we can run from backend/scripts/ or backend/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cron_generator")

# Initialize Firebase
try:
    if not firebase_admin._apps:
        cred_path = os.path.join(os.path.dirname(__file__), '../serviceAccountKey.json')
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("✅ Firestore connected successfully.")
except Exception as e:
    logger.error(f"❌ Failed to connect to Firestore: {e}")
    sys.exit(1)

# API Setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY not found in .env")
    sys.exit(1)

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
SESSION = requests.Session()
SESSION.headers.update({"Content-Type": "application/json"})
SESSION.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504]))
)

# Syllabus
NTA_SYLLABUS = {
    "Physics": [
        "Units and Measurements","Kinematics","Laws of Motion","Work Energy Power",
        "Rotational Motion","Gravitation","Thermodynamics","Kinetic Theory","Waves",
        "Electrostatics","Current Electricity","Magnetism","EM Induction and AC",
        "Optics","Modern Physics"
    ],
    "Chemistry": [
        "Some Basic Concepts of Chemistry","Atomic Structure","Chemical Bonding",
        "States of Matter","Thermodynamics","Equilibrium","Redox Reactions",
        "s-Block Elements","p-Block Elements","d- and f- Block Elements",
        "Coordination Compounds","Organic Chemistry Basics","Hydrocarbons",
        "Haloalkanes and Haloarenes","Alcohols Phenols Ethers","Aldehydes Ketones Acids",
        "Amines","Biomolecules","Polymers","Chemistry in Everyday Life"
    ],
    "Maths": [
        "Sets Relations Functions","Complex Numbers","Quadratic Equations","Sequences and Series",
        "Trigonometry","Matrices Determinants","Limits Continuity Differentiability",
        "Applications of Derivatives","Integrals","Differential Equations",
        "Vectors","3D Geometry","Probability","Binomial Theorem","Statistics"
    ]
}

def generate_questions(subject: str, topic: str, count: int) -> List[Dict[str, Any]]:
    prompt = f"""You are an expert question creator and tutor for the Indian JEE Mains exam.

Generate {count} original, high-quality MCQs for {subject} on the specific topic '{topic}'.

Strict rules:
- The questions MUST match the exact difficulty, depth, and style of real-world JEE Mains questions (e.g., involving multi-concept applications, statement-based questions, or complex numerical setups).
- Format the question text professionally with clear paragraph breaks using '\\n'. Use standard unicode for math/chemistry symbols.
- Provide clear, distinct options. 
- Each item must be a JSON object with EXACTLY these keys:
  "question" (string), 
  "options" (array of 4 strings), 
  "answer_index" (integer 0-3), 
  "topic" (string),
  "hint" (string - a short clue to help the student),
  "explanation" (string - a detailed step-by-step solution formatted beautifully with '\\n' for newlines).
- Output ONLY a valid JSON array (no extra text or markdown)."""

    url = f"{GEMINI_MODEL_URL}?key={GEMINI_API_KEY}"
    resp = SESSION.post(url, json={"contents":[{"parts":[{"text": prompt}]}]}, timeout=60)
    resp.raise_for_status()
    
    ai_json = resp.json()
    text = ai_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    
    if text.startswith("```"):
        text = text.strip("`").replace("json", "", 1).strip()
        
    data = json.loads(text)
    if not isinstance(data, list):
        data = [data]
        
    # Normalize
    cleaned = []
    for q in data:
        try:
            ai = int(q["answer_index"])
            opts = q["options"]
            cleaned.append({
                "subject": subject,
                "topic": q.get("topic", topic),
                "question": q["question"],
                "options": opts,
                "answer_index": ai,
                "correctAnswer": opts[ai],
                "hint": q.get("hint", ""),
                "explanation": q.get("explanation", ""),
                "source": "cron_ai_generated",
                "createdAt": firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            logger.warning(f"Skipping malformed question: {e}")
            
    return cleaned

def save_to_db(questions: List[Dict[str, Any]]):
    if not questions:
        return
        
    col = db.collection("questions")
    batch = db.batch()
    
    for q in questions:
        doc_ref = col.document()
        q["id"] = doc_ref.id
        batch.set(doc_ref, q)
        
    batch.commit()
    logger.info(f"✅ Saved {len(questions)} new questions to Firestore.")

def run_cron_job(target_questions: int = 150):
    """
    Generates target_questions by randomly picking subjects and topics.
    Crucially, sleeps between requests to NEVER exceed the 15 RPM limit.
    """
    logger.info(f"🚀 Starting Cron Job: Goal is to generate {target_questions} questions.")
    
    questions_generated = 0
    batch_size = 10  # 10 questions per API call
    
    # 10 Requests Per Minute = 1 request every 6 seconds. 
    # We use 7 seconds to be completely safe and never hit the limit.
    sleep_time = 7.0 
    
    while questions_generated < target_questions:
        # Pick a random subject and topic
        subject = random.choice(list(NTA_SYLLABUS.keys()))
        topic = random.choice(NTA_SYLLABUS[subject])
        
        logger.info(f"Generating {batch_size} questions for {subject} -> {topic}...")
        
        try:
            questions = generate_questions(subject, topic, batch_size)
            if questions:
                save_to_db(questions)
                questions_generated += len(questions)
                logger.info(f"Progress: {questions_generated}/{target_questions} questions.")
            else:
                logger.warning("AI returned 0 valid questions.")
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning("⚠️ Hit Rate Limit (429). Sleeping for 30 seconds...")
                time.sleep(30)
                continue
            else:
                logger.error(f"API Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            
        if questions_generated < target_questions:
            logger.info(f"Sleeping for {sleep_time} seconds to respect API rate limits...")
            time.sleep(sleep_time)

    logger.info("🎉 Cron job finished successfully!")

if __name__ == "__main__":
    # You can change this number to generate more or fewer questions per run
    TARGET = 100 
    run_cron_job(target_questions=TARGET)
