
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
print(f"Testing Key: {api_key[:5]}...")

try:
    genai.configure(api_key=api_key)
    print("Listing models...", flush=True)
    for m in genai.list_models():
        print(f"Found model: {m.name}", flush=True)
        if 'generateContent' in m.supported_generation_methods:
            print(f" - Supports generateContent", flush=True)
    print("List complete.", flush=True)
except Exception as e:
    import traceback
    print("FATAL ERROR OCCURRED:", flush=True)
    traceback.print_exc()
    print(f"Error Message: {e}", flush=True)
