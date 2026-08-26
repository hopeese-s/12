# Vercel Serverless Function Entrypoint
import os
import sys

# Add parent directory to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
