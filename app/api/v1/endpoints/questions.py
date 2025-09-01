# questions.py - Updated with better error handling
import os, time, json, requests
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Firebase Admin SDK Imports
import firebase_admin
from firebase_admin import credentials, firestore

# --- Firebase Initialization ---
if not firebase_admin._apps:
    try:
        # Initialize Firebase with the provided config
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': os.getenv('NEXT_PUBLIC_FIREBASE_PROJECT_ID', 'ai-powerd-jee-learn')
        })
        logger.info("✅ Firebase App Initialized Successfully.")
    except Exception as e:
        logger.warning(f"⚠️ WARNING: Could not initialize Firebase Admin. Error: {e}")

# Get a reference to the Firestore database client
try:
    db = firestore.client()
    logger.info("✅ Firestore client initialized successfully.")
except Exception as e:
    db = None
    logger.warning(f"⚠️ WARNING: Could not initialize Firestore client: {e}")

router = APIRouter(tags=["questions"])

# ---------- NTA syllabus (expand anytime) ----------
NTA_SYLLABUS: Dict[str, List[str]] = {
    "Physics": [
        "Units and Measurements","Kinematics","Laws of Motion","Work Energy Power",
        "Rotational Motion","Gravitation","Thermodynamics","Kinetic Theory",
        "Waves","Electrostatics","Current Electricity","Magnetism",
        "EM Induction and AC","Optics","Modern Physics"
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

def _get_gemini_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set on backend")
    return key

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"

class GenerateRequest(BaseModel):
    subject: str
    mode: str # 'quick', 'topic', or 'full'
    topic: Optional[str] = None

class ProgressRequest(BaseModel):
    questionId: str
    isCorrect: bool
    isBookmarked: bool

class ExplanationRequest(BaseModel):
    question: str
    options: List[str]
    correctAnswer: str
    userAnswer: str

def _prompt(subject: str, topic: Optional[str], count: int) -> str:
    topic_line = f" on the specific topic of '{topic}'" if topic and topic != "random" else " covering various important topics from the entire syllabus"
    return f"""
You are an expert question creator for the Indian JEE Mains engineering entrance exam.
Your primary directive is to generate {count} new, completely original, high-quality multiple-choice questions (MCQs).

**Strict Instructions:**
1.  **Syllabus Adherence:** The questions MUST strictly adhere to the latest official NTA syllabus for JEE Mains for the subject '{subject}'.
2.  **Uniqueness:** Each question must be unique.
3.  **Format:** Provide the output ONLY in a valid JSON array format. Do not add any text, comments, or markdown formatting like ```json.
4.  **JSON Structure:** Each object in the array must have these exact keys: "question", "options" (an array of 4 strings), "answer_index" (a number from 0 to 3), "hint", "explanation", and "topic".

Generate a JSON array of exactly {count} questions for {subject}{topic_line} now.
""".strip()

def _call_gemini(prompt: str) -> List[Dict[str, Any]]:
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    url = f"{GEMINI_URL}?key={_get_gemini_key()}"
    try:
        r = requests.post(url, json=payload, timeout=90)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"AI connection error: {str(e)}")

    data = r.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"): text = text.strip("` \njson")
        items = json.loads(text)
        if not isinstance(items, list): raise ValueError("Response is not a JSON array")
        return items
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"AI parse error: {e} | Response was: {text}")

def _call_gemini_single(prompt: str) -> str:
    """Helper function to call Gemini for single text response"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    url = f"{GEMINI_URL}?key={_get_gemini_key()}"
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return text
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return "Explanation not available at the moment."

@router.get("/topics")
def list_topics(subject: str = Query(..., pattern="^(Physics|Chemistry|Maths)$")):
    return {"subject": subject, "topics": NTA_SYLLABUS.get(subject, [])}

@router.post("/generate-quiz")
def generate_quiz(req: GenerateRequest):
    subject = req.subject
    mode = req.mode

    if mode == "topic" and (not req.topic or req.topic not in NTA_SYLLABUS.get(subject, [])):
        raise HTTPException(status_code=400, detail="A valid topic is required for topic-wise mode")
    
    count = 5 if mode == "quick" else 30 if mode == "full" else 10

    prompt = _prompt(subject, req.topic, count)
    items = _call_gemini(prompt)

    cleaned = []
    for q in items[:count]:
        try:
            answer_index = int(q["answer_index"])
            cleaned.append({
                "id": None, # We will fill this with the real Firestore ID later
                "subject": subject, "topic": q.get("topic", req.topic or "Mixed"),
                "question": q["question"], "options": q["options"], "answer_index": answer_index,
                "correctAnswer": q["options"][answer_index],
                "hint": q.get("hint", "No hint available."), "explanation": q.get("explanation", "No explanation available.")
            })
        except Exception as e:
            logger.error(f"Skipping malformed AI item: {e}")
            continue

    if not cleaned:
        raise HTTPException(status_code=502, detail="AI generated malformed data. Please try again.")
    
    # --- START: New Firebase Saving Logic ---
    if db: # Check if Firestore was initialized successfully
        logger.info(f"Saving {len(cleaned)} questions to Firestore...")
        questions_collection = db.collection("questions")
        try:
            for question_data in cleaned:
                # Let Firestore create a new document with an automatic ID
                doc_ref = questions_collection.document()
                # Update the 'id' in our list with the real ID from Firestore
                question_data['id'] = doc_ref.id
                # Save the complete question data to the document
                doc_ref.set(question_data)
            logger.info(f"✅ Successfully saved {len(cleaned)} questions to Firestore.")
        except Exception as e:
            # If saving fails, we just print an error but don't stop the user from getting their quiz.
            logger.error(f"❌ ERROR: Could not save questions to Firestore: {e}")
    # --- END: New Firebase Saving Logic ---

    return {"questions": cleaned, "quizTitle": f"{subject} - {mode.replace('_', ' ').title()} Practice"}

@router.post("/record-progress")
def record_progress(req: ProgressRequest):
    """Placeholder for progress tracking"""
    return {"status": "success", "message": "Progress recorded (demo mode)"}

@router.post("/generate-explanation")
async def generate_explanation(request: dict = Body(...)):
    """Generate AI explanation for a question - handles both Pydantic model and raw dict"""
    try:
        # Extract data from request - handle both Pydantic model and raw dict
        if isinstance(request, dict):
            question = request.get("question")
            options = request.get("options", [])
            correct_answer = request.get("correctAnswer")
            user_answer = request.get("userAnswer", "")
        else:
            # This handles the case where FastAPI converts to Pydantic model
            question = request.question
            options = request.options
            correct_answer = request.correctAnswer
            user_answer = request.userAnswer
        
        # Validate required fields
        if not question or not options or not correct_answer:
            logger.warning("Missing required fields in explanation request")
            return {"explanation": "Missing required question data."}
        
        prompt = f"""
        Explain why the correct answer is "{correct_answer}" for this question:
        
        Question: {question}
        
        Options:
        {chr(10).join([f"{i+1}. {opt}" for i, opt in enumerate(options)])}
        
        The user answered: "{user_answer if user_answer else 'No answer provided'}"
        
        Provide a detailed, educational explanation suitable for JEE Mains preparation.
        Explain the concept, why the correct answer is right, and why the user's answer (if wrong) is incorrect.
        """
        
        explanation = _call_gemini_single(prompt)
        return {"explanation": explanation}
    
    except Exception as e:
        logger.error(f"Error generating explanation: {e}")
        correct_answer = request.get("correctAnswer", "the correct option") if isinstance(request, dict) else getattr(request, "correctAnswer", "the correct option")
        return {"explanation": f"Correct answer: {correct_answer}. This question tests important concepts for JEE Mains. Review the related topic for better understanding."}