import sys
sys.path.insert(0, '.')
from database.db import get_db_connection

conn = get_db_connection()
emgs = [dict(r) for r in conn.execute("SELECT id, emergency_id, status, user_id, created_at FROM emergencies WHERE status NOT IN ('RESOLVED', 'CLOSED', 'STAND_DOWN', 'CANCELLED')").fetchall()]
incs = [dict(r) for r in conn.execute("SELECT id, incident_id, status, student_id, created_at FROM incidents WHERE status NOT IN ('RESOLVED', 'CLOSED', 'STAND_DOWN', 'CANCELLED')").fetchall()]

print(f"Active emergencies in DB: {len(emgs)}")
for e in emgs:
    print(" ", e)

print(f"Active incidents in DB: {len(incs)}")
for i in incs:
    print(" ", i)

conn.close()
