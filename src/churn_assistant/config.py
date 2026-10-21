import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
SESSION_DATE = date.fromisoformat(os.getenv("SESSION_DATE", "2026-10-15"))
DATA_DIR = os.getenv("DATA_DIR", "data")
