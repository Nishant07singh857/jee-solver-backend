# questions.py — stable & production-safe
# --------------------------------------
import os, json, requests, logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Optional: load .env if you use python-dotenv (safe if missing)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("questions")

# ---------- Firebase (optional) ----------
db = None
try:
    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        try:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {
                "projectId": os.getenv("NEXT_PUBLIC_FIREBASE_PROJECT_ID", "ai-powerd-jee-learn")
            })
            logger.info("✅ Firebase App initialized.")
        except Exception as e:
            logger.warning(f"⚠️ Firebase init skipped: {e}")

    try:
        db = firestore.client()
        logger.info("✅ Firestore client ready.")
    except Exception as e:
        logger.warning(f"⚠️ Firestore unavailable: {e}")
        db = None
except Exception as e:
    logger.warning(f"⚠️ Firebase modules not loaded: {e}")
    db = None

# ---------- Router ----------
router = APIRouter(tags=["questions"])

# ---------- Constants ----------
GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"

NTA_SYLLABUS: Dict[str, List[str]] = {
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
    ],
}

# ---------- Models ----------
class GenerateRequest(BaseModel):
    subject: str
    mode: str  # 'quick' | 'topic' | 'full'
    topic: Optional[str] = None

class ProgressRequest(BaseModel):
    questionId: str
    isCorrect: bool
    isBookmarked: bool

# ---------- Helpers ----------
def _get_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set on backend")
    return key

# resilient HTTP session with retries/backoff
SESSION = requests.Session()
SESSION.headers.update({"Content-Type": "application/json"})
SESSION.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=4,
            backoff_factor=1.3,  # 1.3s, 2.6s, 5.2s, ...
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={"POST", "GET"},
            raise_on_status=False,
        )
    ),
)

def _prompt(subject: str, topic: Optional[str], count: int) -> str:
    topic_line = (
        f" on the specific topic '{topic}'"
        if topic and topic != "random"
        else " covering key topics from the official NTA syllabus"
    )
    return f"""You are an expert question creator for the Indian JEE Mains exam.

Generate {count} original MCQs for {subject}{topic_line}.

Strict rules:
- Follow the latest NTA syllabus; ensure correctness.
- Each item must be a JSON object with keys EXACTLY:
  "question", "options" (array of 4 strings), "answer_index" (0..3),
  "hint", "explanation", "topic".
- Output ONLY a valid JSON array (no extra text or markdown, no code fences)."""

def _gemini_call(prompt: str, timeout_sec: int = 180) -> dict:
    url = f"{GEMINI_MODEL_URL}?key={_get_key()}"
    try:
        resp = SESSION.post(url, json={"contents":[{"parts":[{"text": prompt}]}]}, timeout=timeout_sec)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.error("Gemini timeout")
        raise HTTPException(status_code=504, detail="AI timed out, please try again")
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini connection error: {e}")
        raise HTTPException(status_code=502, detail=f"AI connection error: {e}")

def _extract_text(ai_json: dict) -> str:
    text = (
        ai_json.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
        .strip()
    )
    # Strip common code-fence wrappers if model added them
    if text.startswith("```"):
        # remove fences like ```json ... ```
        text = text.strip().strip("`")
        text = text.replace("json", "", 1).strip()
    return text

def _to_questions(text: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("Not a JSON array")
        return data
    except Exception as e:
        logger.error(f"Parse error: {e} | head: {text[:300]}")
        raise HTTPException(status_code=502, detail="AI returned malformed JSON")

def _normalize(items: List[Dict[str, Any]], subject: str, fallback_topic: Optional[str]) -> List[Dict[str, Any]]:
    cleaned = []
    for q in items:
        try:
            ai = int(q["answer_index"])
            opts = q["options"]
            cleaned.append({
                "id": None,
                "subject": subject,
                "topic": q.get("topic", fallback_topic or "Mixed"),
                "question": q["question"],
                "options": opts,
                "answer_index": ai,
                "correctAnswer": opts[ai],
                "hint": q.get("hint", "No hint available."),
                "explanation": q.get("explanation", "No explanation available.")
            })
        except Exception as e:
            logger.warning(f"Skipping malformed item: {e}")
    return cleaned

# ---------- Endpoints ----------
@router.get("/topics")
def list_topics(subject: str = Query(..., pattern="^(Physics|Chemistry|Maths)$")):
    return {"subject": subject, "topics": NTA_SYLLABUS.get(subject, [])}

@router.post("/generate-quiz")
def generate_quiz(req: GenerateRequest):
    subject = req.subject
    mode = req.mode

    if subject not in NTA_SYLLABUS:
        raise HTTPException(status_code=400, detail="Invalid subject")

    if mode == "topic" and (not req.topic or req.topic not in NTA_SYLLABUS[subject]):
        raise HTTPException(status_code=400, detail="A valid topic is required for topic-wise mode")

    target = 5 if mode == "quick" else 30 if mode == "full" else 10
    batch = 5  # generate in small chunks to avoid timeouts
    out: List[Dict[str, Any]] = []

    while len(out) < target:
        need = min(batch, target - len(out))
        prompt = _prompt(subject, req.topic, need)
        ai_json = _gemini_call(prompt)         # retries + long timeout inside
        text = _extract_text(ai_json)
        items = _to_questions(text)
        out.extend(_normalize(items[:need], subject, req.topic))

        if len(out) == 0:
            # safety: if model fails to follow JSON, break to avoid loop
            raise HTTPException(status_code=502, detail="AI returned unusable data. Please try again.")

    # Optional Firestore save (best-effort)
    if db:
        try:
            col = db.collection("questions")
            for q in out:
                ref = col.document()
                q["id"] = ref.id
                ref.set(q)
            logger.info(f"✅ Saved {len(out)} questions to Firestore.")
        except Exception as e:
            logger.warning(f"Firestore save skipped: {e}")

    return {
        "questions": out,
        "quizTitle": f"{subject} - {mode.title()} Practice",
        "message": "Quiz generated successfully!"
    }

@router.post("/generate-explanation")
def generate_explanation(payload: Dict[str, Any] = Body(...)):
    question = payload.get("question")
    options = payload.get("options", [])
    correct_answer = payload.get("correctAnswer")
    user_answer = payload.get("userAnswer", "")

    if not question or not options or correct_answer is None:
        return {"explanation": "Missing required fields."}

    prompt = f"""
Explain clearly why the correct answer is "{correct_answer}" for the following MCQ.
Question: {question}
Options:
{chr(10).join([f"{i+1}. {opt}" for i, opt in enumerate(options)])}
User selected: "{user_answer if user_answer else 'No answer'}"
Provide a short, JEE-Mains-level explanation: concept, why correct is correct, and why wrong options are wrong.
""".strip()

    try:
        ai_json = _gemini_call(prompt, timeout_sec=120)
        text = _extract_text(ai_json)
        return {"explanation": text or "Explanation temporarily unavailable."}
    except HTTPException:
        return {"explanation": "Explanation temporarily unavailable. Please try again."}

@router.post("/record-progress")
def record_progress(req: ProgressRequest):
    # placeholder
    return {"status": "success", "message": "Progress recorded (demo mode)"}
