"""
CampusGuard AI — Security Utilities & Middleware
"""

from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db_connection


def hash_password(password: str) -> str:
    """Returns a secure PBKDF2/SHA256 password hash."""
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verifies plaintext password against its stored hash."""
    if not password_hash or not password:
        return False
    return check_password_hash(password_hash, password)


def is_brute_force_locked(identifier: str, threshold: int = 5, window_minutes: int = 15) -> bool:
    """
    Checks if a register number / email has exceeded maximum allowed failed attempts.
    """
    conn = get_db_connection()
    try:
        failed_count = conn.execute(f"""
            SELECT COUNT(*) as cnt FROM login_attempts 
            WHERE UPPER(register_number) = UPPER(?) 
              AND success = 0 
              AND attempt_time >= datetime('now', '-{window_minutes} minutes')
        """, (identifier.strip(),)).fetchone()['cnt']
        return failed_count >= threshold
    except Exception:
        return False
    finally:
        conn.close()


def record_login_attempt(identifier: str, ip_address: str, success: bool):
    """
    Logs every authentication attempt for security auditing and anomaly prevention.
    """
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO login_attempts (register_number, ip_address, success)
            VALUES (?, ?, ?)
        """, (identifier.strip().upper(), ip_address or '127.0.0.1', 1 if success else 0))
        conn.commit()
    except Exception as e:
        print(f"[Security] Failed to record login attempt: {e}")
    finally:
        conn.close()


def add_security_headers(response):
    """
    Prevents browsers from caching protected authentication & dashboard pages,
    and sets basic modern HTTP security headers.
    """
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response
