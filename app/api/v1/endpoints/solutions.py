from fastapi import APIRouter, File, UploadFile, HTTPException
from app.services.llm_service import llm_service

# English: This file defines the API endpoint for the doubt solver feature.
# Hinglish: Yeh file doubt solver feature ke liye API endpoint define karti hai.

router = APIRouter()

@router.post("/solve-image")
async def solve_doubt_from_image(file: UploadFile = File(...)):
    """
    English: Receives an image of a math problem, processes it, and returns a solution.
    Hinglish: Ek math problem ki image receive karta hai, use process karta hai, aur solution return karta hai.
    """
    # English: Check if the uploaded file is an image.
    # Hinglish: Check karte hain ki uploaded file ek image hai ya nahi.
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    # --- Step 1: Image to Text (OCR) ---
    # English: In a real app, you would send the image to an OCR service like Mathpix.
    # Hinglish: Ek real app me, aap image ko Mathpix jaise OCR service ko bhejenge.
    # For this example, we will simulate the OCR output.
    # Is example ke liye, hum OCR output ko simulate karenge.
    
    # simulated_ocr_text = ocr_service.convert_image_to_text(await file.read())
    simulated_ocr_text = "Find the derivative of x^2 + 2x"
    
    if not simulated_ocr_text:
        raise HTTPException(status_code=500, detail="Could not read text from the image.")

    # --- Step 2: Get Solution from LLM Service ---
    # English: We pass the extracted text to our LLM service to get the solution.
    # Hinglish: Hum solution paane ke liye extracted text ko apne LLM service me pass karte hain.
    print(f"Sending query to LLM: {simulated_ocr_text}")
    
    solution_data = llm_service.get_solution_for_query(simulated_ocr_text)
    
    if solution_data["status"] == "error":
        raise HTTPException(status_code=502, detail=solution_data["message"])

    # --- Step 3: Return the final solution ---
    # English: We return the solution received from the AI.
    # Hinglish: Hum AI se mila solution return karte hain.
    return {
        "original_query": simulated_ocr_text,
        "solution": solution_data["solution"]
    }
