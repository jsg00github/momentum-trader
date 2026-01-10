
import os
import uvicorn

if __name__ == "__main__":
    # Get port from environment variable, default to 8000
    # Railway provides PORT as a string, e.g. "5432"
    port_str = os.environ.get("PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        print(f"Warning: Invalid PORT '{port_str}', defaulting to 8000")
        port = 8000
        
    print(f"Starting server on port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
