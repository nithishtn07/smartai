"""
CampusGuard AI — Formatting Utilities
"""

import datetime


def format_currency(amount: float) -> str:
    """Formats numeric amounts to standard INR currency strings."""
    try:
        return f"₹{float(amount):,.2f}"
    except (ValueError, TypeError):
        return f"₹{amount}"


def format_datetime(dt_str: str, output_fmt: str = "%d %b %Y, %I:%M %p") -> str:
    """Parses standard ISO or SQL datetime strings into human-friendly format."""
    if not dt_str:
        return ""
    try:
        # Try parsing ISO or SQLite timestamp
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
            try:
                dt = datetime.datetime.strptime(dt_str.split("+")[0].strip(), fmt)
                return dt.strftime(output_fmt)
            except ValueError:
                continue
        return dt_str
    except Exception:
        return dt_str


def format_status_badge(status: str) -> dict:
    """Returns CSS class and icon for given status strings."""
    st = (status or '').upper()
    if st in ('ACTIVE', 'PASS', 'PAID', 'RESOLVED', 'COMPLETED', 'CONFIRMED', 'APPROVED'):
        return {'class': 'badge-success', 'icon': 'check-circle', 'label': status}
    elif st in ('PENDING', 'SUBMITTED', 'IN_PROGRESS', 'UNDER REVIEW', 'ASSIGNED'):
        return {'class': 'badge-warning', 'icon': 'clock', 'label': status}
    elif st in ('ABSENT', 'FAIL', 'CRITICAL', 'REJECTED', 'CANCELLED', 'OVERDUE'):
        return {'class': 'badge-danger', 'icon': 'alert-circle', 'label': status}
    return {'class': 'badge-secondary', 'icon': 'info', 'label': status}
