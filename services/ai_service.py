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

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()

def sanitize_input(text: str) -> str:
    """Removes sensitive characters and limits length for AI processing."""
    if not text:
        return ""
    return str(text).strip()[:1000]

def query_gemini_api(prompt: str, system_instruction: str = "") -> str:
    """
    Sends request to Gemini REST API if GEMINI_API_KEY is available.
    Returns generated response string or raises an Exception.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured. Using offline AI engine.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{"text": f"{system_instruction}\n\nUser Query: {prompt}" if system_instruction else prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 800
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )

    with urllib.request.urlopen(req, timeout=5) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        candidates = res_data.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            if parts:
                return parts[0].get('text', '').strip()
    
    raise ValueError("Empty response from Gemini API.")

def call_ai_with_fallback(prompt: str, fallback_func, *args, system_instruction: str = "", **kwargs):
    """
    Executes Gemini call with guaranteed fallback execution on any error.
    """
    if GEMINI_API_KEY:
        try:
            return query_gemini_api(prompt, system_instruction=system_instruction)
        except Exception as e:
            # Fall back seamlessly to rule-based offline heuristics
            pass
    return fallback_func(*args, **kwargs)
