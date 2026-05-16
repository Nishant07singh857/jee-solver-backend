import os
import sys
import json
import time
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─── Setup ────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ─── Config ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

NTA_SYLLABUS = {
    "Physics": [
        "Units and Measurements", "Kinematics", "Laws of Motion", "Work Energy Power",
        "Rotational Motion", "Gravitation", "Thermodynamics", "Kinetic Theory", "Waves",
        "Electrostatics", "Current Electricity", "Magnetism", "EM Induction and AC",
        "Optics", "Modern Physics"
    ],
    "Chemistry": [
        "Some Basic Concepts of Chemistry", "Atomic Structure", "Chemical Bonding",
        "States of Matter", "Thermodynamics", "Equilibrium", "Redox Reactions",
        "p-Block Elements", "d- and f- Block Elements", "Coordination Compounds",
        "Organic Chemistry Basics", "Hydrocarbons", "Haloalkanes and Haloarenes",
        "Alcohols Phenols Ethers", "Aldehydes Ketones Acids", "Amines", "Biomolecules"
    ],
    "Maths": [
        "Sets Relations Functions", "Complex Numbers", "Quadratic Equations",
        "Sequences and Series", "Trigonometry", "Matrices Determinants",
        "Limits Continuity Differentiability", "Applications of Derivatives",
        "Integrals", "Differential Equations", "Vectors", "3D Geometry",
        "Probability", "Binomial Theorem", "Statistics"
    ],
}

# ─── HTTP Session ─────────────────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({"Content-Type": "application/json"})
SESSION.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
    ),
)

# ─── Firestore ────────────────────────────────────────────────────────────────
db = None
try:
    import firebase_admin
    from firebase_admin import firestore
    try:
        db = firestore.client()
        print("✅ Firestore connected.")
    except Exception as e:
        print(f"⚠️  Firestore unavailable: {e}")
except Exception as e:
    print(f"⚠️  Firebase not loaded: {e}")

# ─── Helpers ──────────────────────────────────────────────────────────────────
def _gemini_call(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in backend/.env")
    url = f"{GEMINI_MODEL_URL}?key={GEMINI_API_KEY}"
    resp = SESSION.post(
        url,
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=180
    )
    resp.raise_for_status()
    data = resp.json()
    return (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
        .strip()
    )

def _clean_json(text: str) -> str:
    if text.startswith("```"):
        text = text.strip().strip("`")
        text = text.replace("json", "", 1).strip()
    return text

def generate_batch(subject: str, topic: str, count: int = 5) -> int:
    """Generate `count` IIT-level questions for subject/topic and save to Firestore."""
    print(f"\n  📚 {subject} > {topic} ({count} questions)...")

    prompt = f"""You are an elite IIT JEE Advanced question setter.

Generate {count} original, extremely high-difficulty MCQs for {subject} on the topic '{topic}'.

Rules:
- IIT JEE Advanced difficulty ONLY. Multi-concept, numerical, assertion-reason or application-based.
- Options must contain plausible distractors based on common student mistakes.
- Each item is a JSON object with EXACTLY these keys:
  "question" (string), "options" (array of 4 strings), "answer_index" (int 0-3),
  "topic" (string), "hint" (string), "explanation" (string with full step-by-step solution).
- Output ONLY a valid JSON array. No markdown, no extra text."""

    try:
        raw = _gemini_call(prompt)
        raw = _clean_json(raw)
        items = json.loads(raw)
        if not isinstance(items, list):
            items = [items]
    except Exception as e:
        print(f"  ❌ Parse error: {e}")
        return 0

    valid = []
    for q in items:
        try:
            ai = int(q["answer_index"])
            opts = q["options"]
            valid.append({
                "subject": subject,
                "topic": q.get("topic", topic),
                "question": q["question"],
                "options": opts,
                "answer_index": ai,
                "correctAnswer": opts[ai],
                "hint": q.get("hint", ""),
                "explanation": q.get("explanation", ""),
                "source": "cron_iit_level",
                "difficulty": "IIT Advanced",
            })
        except Exception as e:
            print(f"  ⚠️  Skipping malformed item: {e}")

    if valid and db:
        try:
            col = db.collection("questions")
            batch = db.batch()
            for q in valid:
                doc_ref = col.document()
                q["id"] = doc_ref.id
                from firebase_admin import firestore as fs
                q["createdAt"] = fs.SERVER_TIMESTAMP
                batch.set(doc_ref, q)
            batch.commit()
            print(f"  ✅ Saved {len(valid)} questions to Firestore.")
        except Exception as e:
            print(f"  ❌ Firestore save failed: {e}")
            return 0
    elif valid and not db:
        print(f"  ⚠️  No DB — would have saved {len(valid)} questions.")

    return len(valid)

# ─── Main ─────────────────────────────────────────────────────────────────────
def run_cron(target: int = 500):
    print(f"\n🚀 Starting IIT JEE Question Bank Generator")
    print(f"   Target: {target} questions")
    print(f"   Sleep: 12s between requests (safe for 10 RPM free tier)")
    print(f"   Estimated time: ~{round(target / 5 * 12 / 60, 1)} minutes\n")

    generated = 0
    subjects = list(NTA_SYLLABUS.keys())

    while generated < target:
        subject = random.choice(subjects)
        topic = random.choice(NTA_SYLLABUS[subject])
        batch_size = min(5, target - generated)

        count = generate_batch(subject, topic, count=batch_size)
        generated += count

        pct = round(generated / target * 100, 1)
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  Progress [{bar}] {generated}/{target} ({pct}%)")

        if generated < target:
            print(f"  ⏳ Sleeping 12s...", end="", flush=True)
            time.sleep(12)
            print(" done")

    print(f"\n🎉 Complete! Generated {generated} IIT JEE questions.")
    print(f"   Your quiz app will now load questions INSTANTLY from Firestore!")

if __name__ == "__main__":
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    if not GEMINI_API_KEY:
        print("❌ ERROR: GEMINI_API_KEY not found in backend/.env")
        print("   Please add: GEMINI_API_KEY=your_key_here")
        sys.exit(1)
    run_cron(target)
