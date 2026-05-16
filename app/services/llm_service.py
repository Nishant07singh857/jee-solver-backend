import os
import requests

# English: This service is responsible for communicating with the Large Language Model (LLM).
# Hinglish: Yeh service Large Language Model (LLM) se baat karne ke liye responsible hai.

# You would get this from your cloud provider (e.g., Google AI Studio)
# Aapko yeh key aapke cloud provider se milegi
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

class LLMService:
    """
    English: A class to interact with the Gemini AI model.
    Hinglish: Gemini AI model ke saath interact karne ke liye ek class.
    """
    def get_solution_for_query(self, math_query: str) -> dict:
        """
        English: Takes a math problem as text and returns a step-by-step solution from the AI.
        Hinglish: Ek math problem ko text form me leta hai aur AI se step-by-step solution laata hai.
        
        Args:
            math_query (str): The math problem, e.g., "Solve for x: 2x + 5 = 15"
        
        Returns:
            dict: A dictionary containing the solution or an error.
        """
        # English: This is the prompt we send to the AI. We ask it to act like a JEE tutor.
        # Hinglish: Yeh woh prompt hai jo hum AI ko bhejte hain. Hum use ek JEE tutor ki tarah act karne ko kehte hain.
        prompt = f"""
        Act as an expert JEE Mains & Advanced tutor.
        Provide a clear, step-by-step solution for the following math problem.
        Explain the concepts and formulas used.
        
        Problem: "{math_query}"
        
        Solution:
        """
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        # Load Balancing: Groq Fallback
        import random
        groq_key = os.getenv("GROQ_API_KEY")
        use_groq = bool(groq_key) and random.choice([True, False])
        
        if use_groq:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                groq_payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7
                }
                resp = requests.post(url, headers=headers, json=groq_payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                solution_text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                return {"status": "success", "solution": solution_text}
            except Exception as e:
                print(f"Groq failed, falling back to Gemini: {e}")
        
        try:
            # English: We make a POST request to the Gemini API.
            # Hinglish: Hum Gemini API ko ek POST request bhejte hain.
            response = requests.post(GEMINI_API_URL, json=payload, timeout=60)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            result = response.json()
            
            # English: Extract the text from the AI's response.
            # Hinglish: AI ke response se text extract karte hain.
            solution_text = result['candidates'][0]['content']['parts'][0]['text']
            
            return {"status": "success", "solution": solution_text}
        
        except requests.exceptions.RequestException as e:
            print(f"Error calling LLM API: {e}")
            return {"status": "error", "message": "Could not connect to the AI service."}
        except (KeyError, IndexError) as e:
            print(f"Error parsing LLM response: {e}")
            return {"status": "error", "message": "Invalid response from the AI service."}

# English: Create a single instance of the service to be used across the app.
# Hinglish: Poore app me use karne ke liye service ka ek single instance banate hain.
llm_service = LLMService()
