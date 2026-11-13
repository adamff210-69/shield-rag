"""
Groq API Client Helper & Dynamic Model Discovery Engine.

Provides utilities for:
- Querying https://api.groq.com/openai/v1/models dynamically using GROQ_API_KEY
- Filtering active text generation LLM models
- Auto-selecting fallback working models for zero-configuration setup
"""

import os
import json
import urllib.request
from typing import Dict, List, Any, Optional

# Curated fallback standard models if offline or no key set
DEFAULT_FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama-3.2-11b-vision-instruct",
    "llama-3.2-1b-preview",
    "llama-3.2-3b-preview",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "deepseek-r1-distill-llama-70b"
]


def fetch_groq_models(api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch dynamically available models from Groq API using provided API key.

    Returns:
        Dict containing:
        - status: str ("success" or "fallback")
        - api_key_provided: bool
        - models: List[str]
        - recommended_model: str
        - details: str
    """
    key = api_key or os.getenv("GROQ_API_KEY")

    if not key:
        return {
            "status": "fallback",
            "api_key_provided": False,
            "models": DEFAULT_FALLBACK_MODELS,
            "recommended_model": DEFAULT_FALLBACK_MODELS[0],
            "details": "No API key provided. Returning standard Groq fallback model list."
        }

    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {key.strip()}",
        "User-Agent": "ShieldRAG-SecurityApp/1.0"
    }

    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                raw_data = response.read().decode("utf-8")
                data = json.loads(raw_data)

                active_models = []
                for m in data.get("data", []):
                    model_id = m.get("id", "")
                    is_active = m.get("active", True)
                    # Filter for LLM text models (exclude whisper audio transcription models)
                    if is_active and "whisper" not in model_id.lower() and "guard" not in model_id.lower():
                        active_models.append(model_id)

                active_models = sorted(list(set(active_models)))

                if active_models:
                    # Pick recommended model (prefer versatile 70b, 8b instant, or first in list)
                    recommended = active_models[0]
                    for preferred in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-8b-8192", "mixtral-8x7b-32768"]:
                        if preferred in active_models:
                            recommended = preferred
                            break

                    return {
                        "status": "success",
                        "api_key_provided": True,
                        "models": active_models,
                        "recommended_model": recommended,
                        "details": f"Successfully retrieved {len(active_models)} active models from Groq API."
                    }

    except Exception as e:
        print(f"[Groq Client Warning] Could not fetch live models from Groq API: {e}")

    return {
        "status": "fallback",
        "api_key_provided": True,
        "models": DEFAULT_FALLBACK_MODELS,
        "recommended_model": DEFAULT_FALLBACK_MODELS[0],
        "details": f"Could not reach Groq API (or key error). Using curated fallback model list."
    }
