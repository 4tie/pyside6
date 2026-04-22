#!/usr/bin/env python3
"""Standalone web server launcher for the FastAPI application.

Run this script to start the web API server independently from the PySide6 desktop app.
The server will be available at http://127.0.0.1:8000
"""
import sys
import uvicorn
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.web.main import app

if __name__ == "__main__":
    print("=" * 60)
    print("Starting PySide6 Freqtrade Web API Server")
    print("=" * 60)
    print("Server URL: http://127.0.0.1:8000")
    print("API Docs:   http://127.0.0.1:8000/docs")
    print("=" * 60)
    
    uvicorn.run(
        "app.web.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,  # Auto-reload in development
        log_level="info"
    )
