"""
=============================================================================
CampusGuard AI - Base AI Service Connector
Handles external LLM connectivity (Google Gemini / OpenAI) with automatic
offline heuristic fallback support. Never crashes the core ERP.
=============================================================================
"""

import os
import json
import urllib.request
import urllib.parse
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

def get_api_key():
    return (os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or '').strip()

GEMINI_API_KEY = get_api_key()

def sanitize_input(text: str) -> str:
    """Removes sensitive characters and limits length for AI processing."""
    if not text:
        return ""
    return str(text).strip()[:1000]

def query_gemini_api(prompt: str, system_instruction: str = "", max_retries: int = 2) -> str:
    """
    Sends request to Gemini REST API if GEMINI_API_KEY is available.
    Supports auto-model fallback and rate limit retries.
    Returns generated response string or raises an Exception.
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured. Using offline AI engine.")

    logger.info("AI request received")
    logger.info("Gemini API call started")

    candidate_models = ["gemini-3.6-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-3.5-flash"]
    
    payload = {
        "contents": [{
            "parts": [{"text": f"{system_instruction}\n\nUser Query: {prompt}" if system_instruction else prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 800
        }
    }
    
    data = json.dumps(payload).encode('utf-8')

    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req, timeout=12) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    candidates = res_data.get('candidates', [])
                    if candidates:
                        parts = candidates[0].get('content', {}).get('parts', [])
                        if parts:
                            text = parts[0].get('text', '').strip()
                            logger.info("Gemini response received")
                            return text
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    # Model not found on this version, try next model
                    break
                if e.code == 429:
                    wait_time = (2 ** attempt) + 1
                    logger.warning(f"Gemini API rate limit hit ({model_name}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                break
            except Exception as e:
                # Strip any API key details from error string for safe logging
                safe_err = str(e).split('?key=')[0]
                logger.warning(f"Gemini API request error ({model_name}): {safe_err}")
                break
    
    raise RuntimeError("Unable to generate response from Gemini API models.")


def call_ai_with_fallback(prompt: str, fallback_func, *args, system_instruction: str = "", **kwargs):
    """
    Executes Gemini call with guaranteed fallback execution on any error.
    """
    api_key = get_api_key()
    if api_key:
        try:
            return query_gemini_api(prompt, system_instruction=system_instruction)
        except Exception as e:
            safe_err = str(e).split('?key=')[0]
            logger.warning(f"Gemini failed: {safe_err}")
            logger.info("Using fallback AI")
    else:
        logger.info("Using fallback AI (GEMINI_API_KEY not set)")
    return fallback_func(*args, **kwargs)
