# C:\Chatbot\config\settings.py

import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

IMAGE_TO_TEXT_MODEL = "nlpconnect/vit-gpt2-image-captioning"
CHAT_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"
TEXT_TO_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"

STYLE_LABELS = [
    "impressionism",
    "surrealism",
    "cubism",
    "realism",
    "abstract art",
    "expressionism",
    "minimalism",
    "digital fantasy art"
]

EMOTION_LABELS = [
    "calm",
    "sadness",
    "joy",
    "melancholy",
    "awe",
    "mystery",
    "fear",
    "tension"
]

COMPOSITION_LABELS = [
    "symmetrical composition",
    "asymmetrical composition",
    "high contrast lighting",
    "soft lighting",
    "warm color palette",
    "cool color palette",
    "minimal composition",
    "crowded composition"
]