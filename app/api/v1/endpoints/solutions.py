from fastapi import APIRouter, File, UploadFile, HTTPException
import google.generativeai as genai
import os
import io
from PIL import Image

router = APIRouter()

@router.post("/solve-image")
async def solve_doubt_from_image(file: UploadFile = File(...)):
    """
    Receives an image of a math problem, processes it, and returns a solution.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    try:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise HTTPException(status_code=500, detail="Gemini key not configured")
        
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        prompt = (
            "You are an expert IIT JEE Tutor. The attached image contains a student's doubt (a Physics, Chemistry, or Math question). "
            "Please provide a clear, step-by-step solution to this problem. "
            "Explain the concepts and formulas used so the student can learn from it."
        )

        response = model.generate_content([prompt, image])
        
        return {
            "original_query": "Image Upload",
            "solution": response.text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Solver Error: {str(e)}")
