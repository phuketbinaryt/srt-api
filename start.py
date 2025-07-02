#!/usr/bin/env python3
"""
Startup script for the Audio Transcription API
"""
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    print(f"Starting Audio Transcription API on {host}:{port}")
    print("Supported formats: mp3, wav, m4a, flac, ogg, wma")
    print("Max file size: 100MB")
    
    # Don't show localhost URL in production
    if port == 8000:
        print("API Documentation: http://localhost:8000/docs")
    else:
        print("API Documentation available at /docs endpoint")
    
    # Disable reload in production (Render)
    reload_enabled = os.getenv("ENVIRONMENT", "development") == "development"
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level="info"
    )