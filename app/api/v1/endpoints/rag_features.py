from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
import os
import io
import json
import re
from PIL import Image

router = APIRouter()

# ─── Load Shared FAISS Brain ──────────────────────────────────────────────────
try:
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings

    FAISS_INDEX_PATH = "faiss_index"
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    rag_brain = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    print("✅ RAG Brain loaded for RAG Features endpoint.")
except Exception as e:
    print(f"⚠️ FAISS not available for RAG Features: {e}")
    rag_brain = None


def get_gemini_model():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="Gemini API key not configured.")
    genai.configure(api_key=key)
    return genai.GenerativeModel("gemini-2.5-flash")


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 1: Custom Mock Test Generator (NCERT-based)
# ═══════════════════════════════════════════════════════════════════════════════

class MockTestRequest(BaseModel):
    subject: str      # e.g. "Physics"
    chapter: str      # e.g. "Thermodynamics"
    num_questions: int = 5  # default 5 MCQs

@router.post("/generate-mock-test")
async def generate_mock_test(request: MockTestRequest):
    """
    Generates hard, NCERT-based MCQs by first retrieving relevant textbook
    chunks from the FAISS vector database and then feeding them to Gemini.
    """
    try:
        model = get_gemini_model()

        # Step 1: Retrieve relevant NCERT content from FAISS
        ncert_context = ""
        if rag_brain:
            search_query = f"{request.subject} {request.chapter} concepts formulas laws"
            docs = rag_brain.similarity_search(search_query, k=6)  # Get 6 relevant chunks
            if docs:
                raw_context = "\n\n---\n\n".join([doc.page_content for doc in docs])
                # Sanitize: remove control characters that break JSON generation
                ncert_context = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', ' ', raw_context)

        # Step 2: Build a powerful prompt grounded in NCERT content
        prompt = f"""You are an elite IIT JEE question setter with 20 years of experience.
Your task is to generate {request.num_questions} extremely hard MCQ questions for IIT JEE on:
Subject: {request.subject}
Chapter: {request.chapter}

{'Use the following official NCERT textbook content as your PRIMARY reference:' if ncert_context else ''}
{'[NCERT REFERENCE]' if ncert_context else ''}
{ncert_context if ncert_context else ''}

STRICT RULES:
1. Each question MUST test deep conceptual understanding, not just memorization.
2. Use multi-concept integration, assertion-reasoning, or tricky numericals.
3. All 4 options must be plausible (no obviously wrong options).
4. Follow the LATEST NTA JEE 2024-25 pattern.
5. Output ONLY a valid JSON array. No extra text before or after.

JSON Format (return EXACTLY this structure):
[
  {{
    "question": "Full question text here",
    "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
    "answer_index": 0,
    "hint": "Short hint",
    "explanation": "Detailed step-by-step explanation with the NCERT concept used"
  }}
]"""

        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Try to extract JSON array from the response robustly
        # Remove markdown code fences
        raw_text = re.sub(r'```json|```', '', raw_text).strip()

        # Find JSON array boundaries
        start_idx = raw_text.find('[')
        end_idx = raw_text.rfind(']') + 1
        if start_idx != -1 and end_idx > start_idx:
            raw_text = raw_text[start_idx:end_idx]

        questions = json.loads(raw_text)

        return {
            "success": True,
            "subject": request.subject,
            "chapter": request.chapter,
            "ncert_grounded": bool(ncert_context),
            "questions": questions
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mock Test Generation Error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 2: Photo to Official Solution (RAG-powered Doubt Solver)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/photo-solve")
async def photo_solve(file: UploadFile = File(...)):
    """
    Accepts a photo of a doubt/question, extracts text with Gemini Vision,
    searches FAISS for the official NCERT solution, and returns a grounded answer.
    """
    try:
        model = get_gemini_model()

        # Step 1: Read and process the image
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))

        # Step 2: Extract the question text from the photo using Gemini Vision
        extract_prompt = (
            "Look at this image carefully. Extract ONLY the question text (the problem statement). "
            "Do not solve it. Just return the plain text of the question in English. "
            "If it's a handwritten attempt, extract the original question being solved."
        )
        question_extract = model.generate_content([extract_prompt, image])
        extracted_question = question_extract.text.strip()

        # Step 3: Search FAISS brain for relevant NCERT content
        ncert_context = ""
        source_found = False
        if rag_brain and extracted_question:
            docs = rag_brain.similarity_search(extracted_question, k=3)
            if docs:
                ncert_context = "\n\n---\n\n".join([doc.page_content for doc in docs])
                source_found = True

        # Step 4: Generate the official, grounded solution
        solve_prompt = f"""You are an expert IIT JEE teacher and examiner.

A student has submitted a question (extracted from their photo):
"{extracted_question}"

{'Here is the relevant official NCERT/textbook content for this topic:' if ncert_context else 'Solve using your JEE expertise:'}
{'[OFFICIAL TEXTBOOK REFERENCE]' if ncert_context else ''}
{ncert_context if ncert_context else ''}

Your task:
1. Identify the concept being tested.
2. State the relevant formula/law from the textbook reference (if provided).
3. Solve step-by-step with clear mathematical working.
4. Box the final answer clearly.
5. Give a one-line NCERT page reference or chapter name where this concept appears.

Format your response in clean sections:
**Concept:** [concept name]
**Formula Used:** [relevant formula]
**Solution:**
[step by step working]
**Final Answer:** [answer]
**NCERT Reference:** [chapter/topic name]"""

        solution_response = model.generate_content(solve_prompt)

        return {
            "success": True,
            "extracted_question": extracted_question,
            "solution": solution_response.text,
            "ncert_grounded": source_found,
            "message": "✅ Solution grounded in NCERT textbook" if source_found else "ℹ️ Solved using AI expertise (NCERT reference not found for this topic)"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Photo Solve Error: {str(e)}")

# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 3: Tinder-Style AI Flashcards (Revision Shorts)
# ═══════════════════════════════════════════════════════════════════════════════
import random

class FlashcardRequest(BaseModel):
    subject: str
    topic: str
    count: int = 5

@router.post("/generate-flashcards")
async def generate_flashcards(request: FlashcardRequest):
    """
    Pulls NCERT chunks and converts them into crisp, one-liner flashcards for mobile revision.
    """
    try:
        model = get_gemini_model()

        ncert_context = ""
        if rag_brain:
            # Add some randomness to the search query so they don't get the exact same flashcards twice
            random_seed = random.choice(["definition", "formula", "important concept", "exception", "fact"])
            search_query = f"{request.subject} {request.topic} {random_seed} NCERT"
            docs = rag_brain.similarity_search(search_query, k=5)
            if docs:
                raw_context = "\n\n".join([doc.page_content for doc in docs])
                ncert_context = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', ' ', raw_context)

        prompt = f"""You are an IIT JEE Revision expert.
Create {request.count} short, punchy flashcards for rapid revision on:
Subject: {request.subject}
Topic: {request.topic}

{'Use this NCERT text as your primary source:' if ncert_context else ''}
{ncert_context if ncert_context else ''}

Rules for the flashcards:
1. They must be extremely short (like a tweet or an Instagram Reel text).
2. The front should be a question, a missing formula, or a concept name.
3. The back should be the direct answer, the exact formula, or a punchy explanation.
4. Output EXACTLY a valid JSON array of objects.

Format:
[
  {{
    "front": "What is the formula for Kinetic Energy?",
    "back": "KE = 1/2 mv²",
    "category": "Formula"
  }}
]"""

        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        raw_text = re.sub(r'```json|```', '', raw_text).strip()
        
        start_idx = raw_text.find('[')
        end_idx = raw_text.rfind(']') + 1
        if start_idx != -1 and end_idx > start_idx:
            raw_text = raw_text[start_idx:end_idx]

        flashcards = json.loads(raw_text)

        return {
            "success": True,
            "subject": request.subject,
            "topic": request.topic,
            "ncert_grounded": bool(ncert_context),
            "flashcards": flashcards
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flashcard Generation Error: {str(e)}")
