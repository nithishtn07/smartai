"""
=============================================================================
CampusGuard AI — Sliding Window Rate Limiter & Brute-Force Defense
=============================================================================
Provides in-memory sliding-window request throttling for security-sensitive
endpoints (authentication, password resets, AI queries, and emergency triggers).
=============================================================================
"""

import time
from functools import wraps
from flask import request, jsonify, flash, redirect, url_for


# In-memory storage: { "key": [timestamp1, timestamp2, ...] }
_REQUEST_BUCKETS = {}


def is_rate_limited(key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """
    Checks if a key (e.g. IP or IP+Endpoint) has exceeded max requests within the sliding window.
    """
    now = time.time()
    cutoff = now - window_seconds

    if key not in _REQUEST_BUCKETS:
        _REQUEST_BUCKETS[key] = [now]
        return False

    # Purge old timestamps
    _REQUEST_BUCKETS[key] = [t for t in _REQUEST_BUCKETS[key] if t > cutoff]

    if len(_REQUEST_BUCKETS[key]) >= max_requests:
        return True

    _REQUEST_BUCKETS[key].append(now)
    return False


def rate_limit(max_requests: int = 15, window_seconds: int = 60, json_response: bool = True):
    """
    Decorator for Flask routes enforcing sliding-window rate limit per client IP.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            
            rate_key = f"{ip}:{request.endpoint or f.__name__}"

            if is_rate_limited(rate_key, max_requests=max_requests, window_seconds=window_seconds):
                if json_response or request.is_json:
                    return jsonify({
                        'status': 'error',
                        'error': 'Too Many Requests',
                        'message': f"Rate limit exceeded. Please wait {window_seconds} seconds before retrying.",
                        'retry_after_seconds': window_seconds
                    }), 429
                else:
                    flash(f"Rate limit exceeded. Please wait a moment before trying again.", "danger")
                    return redirect(request.referrer or url_for('landing'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def clear_rate_limits():
    """Clears all stored rate limit buckets (useful for test resets)."""
    global _REQUEST_BUCKETS
    _REQUEST_BUCKETS.clear()
