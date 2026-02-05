
import ai_advisor
import json
import time

print("Running AI Advisor...")
start = time.time()
recs = ai_advisor.get_recommendations()
end = time.time()

print(f"Time taken: {end - start:.2f}s")
print(json.dumps(recs, indent=2))
