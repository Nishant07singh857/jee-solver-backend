import os, json, requests, logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body, BackgroundTasks
from pydantic import BaseModel
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Optional: load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("questions")

db = None
try:
    import firebase_admin
    from firebase_admin import firestore

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
GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
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

SESSION = requests.Session()
SESSION.headers.update({"Content-Type": "application/json"})
SESSION.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=4,
            backoff_factor=1.3,
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
        else " covering diverse key topics from the official JEE syllabus"
    )

    return f"""You are an elite IIT JEE question paper setter with 20+ years of experience.

Generate {count} original, extremely high-quality MCQs for {subject}{topic_line}.

DIFFICULTY REQUIREMENTS (Non-negotiable):
- Questions must be at FULL IIT JEE Advanced difficulty — NOT Class 12 textbook level.
- Include: multi-concept problems, tricky numerical calculations, application-based reasoning, assertion-reason type, and graph/diagram interpretation questions.
- Each question should require 3-5 minutes to solve for an average JEE aspirant.
- Avoid trivial recall questions (e.g., "What is the SI unit of X?" is NOT acceptable).
- Options must be carefully crafted so that common mistakes land on wrong options (distractors).

QUALITY STANDARDS:
- Questions MUST involve: derivations, formula combinations, edge-case analysis, or multi-step calculations.
- For Physics: Include problems involving FBDs, energy methods, circuit analysis, wave superposition, nuclear physics numericals.
- For Chemistry: Include problems involving reaction mechanisms, multi-equilibria, electrochemistry numericals, organic name reactions with exceptions.
- For Maths: Include problems involving definite integrals, complex number geometry, probability combinations, 3D geometry, matrix applications.

FORMAT:
- Format question text with '\\n' for line breaks. Use proper unicode: α β γ δ θ λ μ π ω Σ ∫ ∂ √ ×10⁻ etc.
- Each item must be a valid JSON object with EXACTLY these keys:
  "question" (string),
  "options" (array of exactly 4 strings),
  "answer_index" (integer 0-3),
  "topic" (string — the specific sub-topic),
  "hint" (string — a one-line conceptual nudge, not the answer),
  "explanation" (string — full step-by-step solution with formulas, at JEE topper quality).
- Output ONLY a valid JSON array. No markdown. No extra text."""

def _enrichment_prompt(question_data: Dict[str, Any]) -> str:
    # 👇 BACKGROUND PROMPT: Generates explanation for DB saving
    return f"""
    For the following JEE Question, provide a "hint" and a detailed "explanation".
    
    Question: {question_data['question']}
    Correct Answer: {question_data['options'][question_data['answer_index']]}
    
    Output ONLY a JSON object with keys: "hint", "explanation".
    """

def _llm_call(prompt: str, timeout_sec: int = 180, force_json: bool = False) -> dict:
    import random
    groq_key = os.getenv("GROQ_API_KEY")
    # Load Balancing: 50% chance Groq, 50% Gemini if Groq key is available
    use_groq = bool(groq_key) and random.choice([True, False])
    
    if use_groq:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            }
            if force_json:
                payload["response_format"] = {"type": "json_object"}
                payload["messages"].insert(0, {"role": "system", "content": "You are a JSON generating API. Always return a valid JSON object/array."})
            
            resp = SESSION.post(url, headers=headers, json=payload, timeout=timeout_sec)
            resp.raise_for_status()
            return {"provider": "groq", "data": resp.json()}
        except Exception as e:
            logger.error(f"Groq failed, falling back to Gemini: {e}")
            # Fallback to Gemini
            pass

    # Gemini (Primary or Fallback)
    url = f"{GEMINI_MODEL_URL}?key={_get_key()}"
    try:
        resp = SESSION.post(url, json={"contents":[{"parts":[{"text": prompt}]}]}, timeout=timeout_sec)
        resp.raise_for_status()
        return {"provider": "gemini", "data": resp.json()}
    except requests.exceptions.Timeout:
        logger.error("Gemini timeout")
        raise HTTPException(status_code=504, detail="AI timed out, please try again")
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini connection error: {e}")
        raise HTTPException(status_code=502, detail=f"AI connection error: {e}")

def _extract_text(ai_resp: dict) -> str:
    provider = ai_resp.get("provider", "gemini")
    data = ai_resp.get("data", ai_resp)
    
    if provider == "groq":
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    else:
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        
    if text.startswith("```"):
        text = text.strip().strip("`")
        text = text.replace("json", "", 1).strip()
    return text

def _to_questions(text: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return [data]
        if not isinstance(data, list):
            raise ValueError("Not a JSON array")
        return data
    except Exception as e:
        logger.error(f"Parse error: {e} | head: {text[:300]}")
        return []

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
                # Set to None so frontend knows to pre-fetch, 
                # and background task knows to generate it for DB
                "hint": q.get("hint", None), 
                "explanation": q.get("explanation", None)
            })
        except Exception as e:
            logger.warning(f"Skipping malformed item: {e}")
    return cleaned

# ---------- Background Task ----------
def enrich_and_save_questions(questions: List[Dict[str, Any]]):
    """
    Background task: Saves the fully generated questions directly to Firestore.
    No extra API calls are made because explanations were generated upfront.
    """
    if not db:
        logger.warning("⚠️ DB not connected, skipping background save.")
        return

    logger.info(f"🚀 Saving {len(questions)} questions to Firestore background pool...")
    
    col = db.collection("questions")
    batch = db.batch()
    
    for q in questions:
        try:
            doc_ref = col.document()
            q["id"] = doc_ref.id
            q["source"] = "ai_generated"
            q["createdAt"] = firestore.SERVER_TIMESTAMP
            
            batch.set(doc_ref, q)
            
        except Exception as e:
            logger.error(f"Failed to process question for DB: {e}")
    
    # Commit all at once
    try:
        batch.commit()
        logger.info(f"✅ Successfully saved {len(questions)} questions to Firestore.")
    except Exception as e:
        logger.error(f"Firestore batch commit failed: {e}")

# ---------- Endpoints ----------
@router.get("/topics")
def list_topics(subject: str = Query(..., pattern="^(Physics|Chemistry|Maths)$")):
    return {"subject": subject, "topics": NTA_SYLLABUS.get(subject, [])}

@router.post("/generate-quiz")
def generate_quiz(req: GenerateRequest, background_tasks: BackgroundTasks):
    subject = req.subject
    mode = req.mode

    if subject not in NTA_SYLLABUS:
        raise HTTPException(status_code=400, detail="Invalid subject")

    target = 5 if mode == "quick" else 30 if mode == "full" else 10
    batch = 10
    out: List[Dict[str, Any]] = []

    # 1. Try to fetch from Firestore first (Lightning Fast)
    if db:
        try:
            col = db.collection("questions")
            query_ref = col.where("subject", "==", subject)
            if req.topic and req.topic != "random":
                query_ref = query_ref.where("topic", "==", req.topic)
            
            # Use limit to avoid massive reads, pull a bit extra to sample
            docs = query_ref.limit(target * 3).stream()
            db_questions = []
            for doc in docs:
                q_data = doc.to_dict()
                q_data["id"] = doc.id
                db_questions.append(q_data)
            
            if len(db_questions) >= target:
                import random
                out = random.sample(db_questions, target)
            elif len(db_questions) > 0:
                out = db_questions # Take whatever we have
        except Exception as e:
            logger.error(f"Error fetching from DB: {e}")

    # 2. Fallback to Gemini if not enough questions in DB (SLOW)
    if len(out) < target:
        needed = target - len(out)
        while len(out) < target:
            need = min(batch, target - len(out))
            prompt = _prompt(subject, req.topic, need)
            try:
                ai_resp = _llm_call(prompt, force_json=True)
                text = _extract_text(ai_resp)
                items = _to_questions(text)
                normalized_items = _normalize(items[:need], subject, req.topic)
                out.extend(normalized_items)
            except Exception:
                if len(out) > 0: break # Return whatever we have if error occurs
                raise HTTPException(status_code=502, detail="AI busy, try again.")
        
        # We only save the NEWLY generated ones to DB (background task)
        if len(out) > 0:
            new_generated = out[-needed:]
            background_tasks.add_task(enrich_and_save_questions, new_generated)

    # 2. Trigger Background Task (SLOW but Invisible to User)
    # 3. Return Fast Response to User
    return {
        "questions": out, 
        "quizTitle": f"{subject} - {mode.title()} Practice",
        "message": "Quiz generated instantly from the bank!" if len(out) == target else "Quiz generated!"
    }

@router.post("/generate-explanation")
def generate_explanation(payload: Dict[str, Any] = Body(...)):
    question = payload.get("question")
    options = payload.get("options", [])
    correct_answer = payload.get("correctAnswer")
    user_answer = payload.get("userAnswer", "")

    # Fix: options can be empty for chat-based calls — only require question
    if not question:
        return {"explanation": "Missing required fields."}

    prompt = f"""
You are an expert JEE Mains tutor. Explain clearly why the correct answer is "{correct_answer}" for the following MCQ.

Question: {question}
Options:
{chr(10).join([f"{i+1}. {opt}" for i, opt in enumerate(options)])}
User selected: "{user_answer if user_answer else 'No answer'}"

Provide a highly readable, step-by-step JEE-Mains-level explanation. 
Structure it with:
1. Concept used
2. Step-by-step derivation/calculation
3. Why the correct answer is correct (and briefly why the user's answer is wrong if they made a mistake).
Format the text beautifully with clear paragraph breaks. Use standard unicode for math/chemistry symbols.
""".strip()

    try:
        ai_resp = _llm_call(prompt, timeout_sec=120, force_json=True)
        text = _extract_text(ai_resp)
        return {"explanation": text or "Explanation temporarily unavailable."}
    except HTTPException:
        return {"explanation": "Explanation temporarily unavailable. Please try again."}

@router.post("/record-progress")
def record_progress(req: ProgressRequest):
    # placeholder
    return {"status": "success", "message": "Progress recorded (demo mode)"}

@router.post("/chat")
def ai_chat(payload: Dict[str, Any] = Body(...)):
    """
    Dedicated endpoint for the AI Doubt Solver chatbot.
    Accepts a free-form student doubt in the context of a JEE question.
    """
    doubt = payload.get("doubt", "").strip()
    question = payload.get("question", "").strip()
    correct_answer = payload.get("correctAnswer", "").strip()
    options = payload.get("options", [])

    if not doubt:
        return {"reply": "Please type your doubt first."}

    # Build a context-aware prompt
    context_block = ""
    if question:
        opts_str = "\n".join([f"{chr(65+i)}. {o}" for i, o in enumerate(options)]) if options else ""
        context_block = f"""
Current JEE question:
Q: {question}
{opts_str}
Correct Answer: {correct_answer if correct_answer else 'Not revealed yet'}
"""

    prompt = f"""You are a friendly, expert IIT JEE tutor (like a topper friend).
{context_block}
Student's doubt: {doubt}

Give a clear, helpful reply in 3-5 sentences maximum. Use simple language. If it's a calculation, show the key steps. Use unicode math symbols (×, ÷, √, α, β, θ, etc.).
Do NOT say 'As an AI'. Be direct and helpful like a human tutor.""".strip()

    try:
        ai_resp = _llm_call(prompt, timeout_sec=60)
        text = _extract_text(ai_resp)
        return {"reply": text or "I couldn't understand that. Can you rephrase your doubt?"}
    except Exception:
        return {"reply": "The AI tutor is busy right now. Try again in a few seconds! ⏳"}