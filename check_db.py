import firebase_admin
from firebase_admin import credentials, firestore
import os

# 1. Firebase Initialize karein
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"❌ Error: serviceAccountKey.json nahi mili ya galat hai.\n{e}")
        exit()

db = firestore.client()

def get_counts():
    print("\n📊 --- Database Report --- 📊\n")
    
    try:
        # 1. Total Questions Count
        total_query = db.collection('questions').count()
        total_snapshot = total_query.get()
        total = total_snapshot[0][0].value
        
        print(f"✅ TOTAL QUESTIONS: {total}")
        print("-" * 30)

        # 2. Subject-wise Count
        subjects = ["Physics", "Chemistry", "Maths"]
        
        for sub in subjects:
            # Note: Subject small letters me ho sakta hai, isliye check karein
            # Hamare code me hum lowercase save kar rahe the (physics, chemistry...)
            query = db.collection('questions').where('subject', '==', sub).count()
            snap = query.get()
            count = snap[0][0].value
            print(f"📚 {sub}: {count}")
            
    except Exception as e:
        print(f"❌ Error fetching data: {e}")

if __name__ == "__main__":
    get_counts()