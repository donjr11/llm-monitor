import os
from dotenv import load_dotenv

load_dotenv()

# Database
DB_PATH = os.getenv("DB_PATH", "./data/llm_monitor.db")

# HuggingFace
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
HF_API_URL = "https://huggingface.co/api/models"

# Collection settings
MIN_MODELS_REQUIRED = 20