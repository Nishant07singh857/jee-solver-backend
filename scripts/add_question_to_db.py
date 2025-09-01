import firebase_admin
from firebase_admin import credentials, firestore
import os

# --- Step 1: Firebase App ko Initialize karein ---
try:
    # Yeh script ke location se key file ka path pata laga lega
    script_dir = os.path.dirname(os.path.abspath(__file__))
    key_path = os.path.join(script_dir, '..', 'serviceAccountKey.json')
    
    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase successfully initialized.")
except Exception as e:
    print(f"❌ Firebase initialization failed: {e}")
    exit()

# --- Step 2: Firestore Database Client banayein ---
db = firestore.client()

def save_question_to_firestore(question_data):
    """
    'jee_questions' collection mein ek naya question document save karta hai.
    """
    try:
        # 'jee_questions' collection mein naya document add karein
        doc_ref = db.collection('jee_questions').add(question_data)
        print(f"🚀 Question successfully saved! Document ID: {doc_ref[1].id}")
    except Exception as e:
        print(f"❌ Error saving question: {e}")

# Yeh block tabhi chalta hai jab script ko seedha run kiya jaata hai
if __name__ == "__main__":
    
    # --- Step 3: Yahan apna question data daalein ---
    my_new_question = {
      "question_text": "A physical quantity Z is related to four measurable quantities a, b, c, and d as follows: Z = a²b²/³ / (c¹/²d³). The percentage errors in the measurement of a, b, c, and d are 1%, 3%, 4%, and 2%, respectively. What is the percentage error in Z?",
      "options": [
        "13%",
        "12%",
        "14%",
        "10%"
      ],
      "correct_answer": "12%",
      "answer_index": 1,
      "hint": "For a quantity X = AᵐBⁿ / CᵖD۹, the maximum percentage error is given by (%Error in X) = m(%Error in A) + n(%Error in B) + p(%Error in C) + q(%Error in D). Errors are always added.",
      "explanation": "The formula for calculating the maximum percentage error is derived from its relation... thus the total error is 12%.",
      "subject": "Physics",
      "topic": "Units and Measurement",
      "difficulty": "Easy",
      "source": "User-Uploaded",
      "tags": ["Error Analysis", "Dimensional Analysis"],
      "created_at": firestore.SERVER_TIMESTAMP # Save hone ka time add karega
    }

    # --- Step 4: Function ko call karke data save karein ---
    save_question_to_firestore(my_new_question)