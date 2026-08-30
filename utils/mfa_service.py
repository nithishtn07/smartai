"""
=============================================================================
CampusGuard AI — Multi-Factor Authentication (TOTP 2FA) Engine
=============================================================================
RFC 6238 compliant Time-Based One-Time Password (TOTP) generator and verifier:
- Compatible with Google Authenticator, Microsoft Authenticator, and Authy
- Generates base32 secret keys and otpauth:// provisioning URIs
- Generates 8 one-time emergency backup recovery codes
- Validates 6-digit TOTP codes with ±1 interval time drift tolerance (30s window)
=============================================================================
"""

import hmac
import hashlib
import time
import struct
import base64
import secrets
from typing import Tuple, List, Dict, Any


def generate_mfa_secret() -> str:
    """Generates a random 16-character base32 secret key."""
    random_bytes = secrets.token_bytes(10)
    return base64.b32encode(random_bytes).decode('utf-8').rstrip('=')


def generate_backup_codes(count: int = 8) -> List[str]:
    """Generates a set of cryptographically secure emergency recovery codes."""
    codes = []
    for _ in range(count):
        code = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
        codes.append(code)
    return codes


def get_totp_token(secret: str, time_step: int = 30, t0: int = 0) -> str:
    """
    Computes current 6-digit TOTP token using HMAC-SHA1 algorithm.
    """
    try:
        # Pad secret to valid base32 length
        padded_secret = secret + '=' * ((8 - len(secret) % 8) % 8)
        key = base64.b32decode(padded_secret, casefold=True)
    except Exception:
        key = secret.encode('utf-8')

    current_time = int(time.time())
    time_counter = int((current_time - t0) / time_step)
    msg = struct.pack(">Q", time_counter)

    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF
    return f"{code % 1000000:06d}"


def verify_totp_token(secret: str, user_code: str, time_step: int = 30, window: int = 1) -> bool:
    """
    Validates user submitted 6-digit token against current, prior, and next interval (±30s).
    """
    if not secret or not user_code or len(user_code.strip()) != 6:
        return False

    user_code = user_code.strip()

    try:
        padded_secret = secret + '=' * ((8 - len(secret) % 8) % 8)
        key = base64.b32decode(padded_secret, casefold=True)
    except Exception:
        key = secret.encode('utf-8')

    current_time = int(time.time())
    base_counter = int(current_time / time_step)

    for offset in range(-window, window + 1):
        time_counter = base_counter + offset
        msg = struct.pack(">Q", time_counter)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        idx = h[-1] & 0x0F
        expected_code = struct.unpack(">I", h[idx:idx+4])[0] & 0x7FFFFFFF
        formatted_expected = f"{expected_code % 1000000:06d}"

        if hmac.compare_digest(formatted_expected, user_code):
            return True

    return False


def get_mfa_provisioning_uri(username: str, secret: str, issuer: str = "CampusGuard AI") -> str:
    """Constructs standard otpauth:// URI for authenticator app QR code generation."""
    return f"otpauth://totp/{issuer}:{username}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
