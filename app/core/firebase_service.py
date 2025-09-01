# File Name: jee-solver-backend/app/core/firebase_service.py
# This is a NEW file.

import firebase_admin
from firebase_admin import credentials, firestore

# IMPORTANT: Apne Firebase project ki service account key file download karein
# aur uska naam 'serviceAccountKey.json' rakh kar backend ke root folder mein rakhein.
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

def get_firestore_db():
    return db
