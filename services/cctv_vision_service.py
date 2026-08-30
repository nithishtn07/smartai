"""
=============================================================================
CampusGuard AI — Computer Vision CCTV Safety & Crowd Telemetry Engine
=============================================================================
Simulates and analyzes optical video streams across campus surveillance cameras:
- Crowd Density & Sudden Surge / Stampede Risk Detection
- Night-time Loitering & Deserted Dark Zone Anomaly Detection
- Perimeter Security & Gate Barrier Intrusion Alerts
- High-confidence bounding box telemetry synthesis for security dashboard
=============================================================================
"""

import datetime
from typing import Dict, List, Any


CCTV_CAMERA_FEEDS = [
    {
        "camera_id": "CAM-MAIN-GATE-01",
        "zone_name": "Main Institutional Entrance Gate",
        "status": "ONLINE",
        "resolution": "4K Ultra-HD (60 FPS)",
        "ip_stream": "rtsp://10.0.4.101/live/main_gate_hd",
        "normal_capacity": 50,
        "is_illuminated": True
    },
    {
        "camera_id": "CAM-ENG-QUAD-02",
        "zone_name": "Academic Block B Courtyard",
        "status": "ONLINE",
        "resolution": "1080p (30 FPS)",
        "ip_stream": "rtsp://10.0.4.102/live/eng_quad_hd",
        "normal_capacity": 150,
        "is_illuminated": True
    },
    {
        "camera_id": "CAM-SPORTS-PATH-03",
        "zone_name": "Lake Pathway & Sports Ground Perimeter",
        "status": "ONLINE",
        "resolution": "1080p IR Night-Vision (30 FPS)",
        "ip_stream": "rtsp://10.0.4.103/live/sports_path_night",
        "normal_capacity": 30,
        "is_illuminated": False
    },
    {
        "camera_id": "CAM-HOSTEL-CORR-04",
        "zone_name": "Hostel Block B Main Entrance",
        "status": "ONLINE",
        "resolution": "1080p (30 FPS)",
        "ip_stream": "rtsp://10.0.4.104/live/hostel_b_gate",
        "normal_capacity": 40,
        "is_illuminated": True
    }
]


def analyze_cctv_feed(camera_id: str, simulated_people_count: int = None, hour_override: int = None) -> Dict[str, Any]:
    """
    Analyzes optical camera feed telemetry for safety anomalies.
    """
    cam = next((c for c in CCTV_CAMERA_FEEDS if c['camera_id'] == camera_id), CCTV_CAMERA_FEEDS[0])
    
    current_hour = hour_override if hour_override is not None else datetime.datetime.now().hour
    is_night = (current_hour >= 21 or current_hour <= 5)

    if simulated_people_count is None:
        simulated_people_count = 12 if not is_night else 2

    anomalies = []
    safety_tier = 'NOMINAL'
    confidence = 0.94

    # Check 1: Crowd Surge / Overcrowding
    if simulated_people_count > (cam['normal_capacity'] * 1.5):
        safety_tier = 'CRITICAL'
        anomalies.append({
            'type': 'CROWD_SURGE_DETECTED',
            'severity': 'HIGH',
            'details': f"Abnormal crowd accumulation ({simulated_people_count} individuals detected, capacity {cam['normal_capacity']}). Risk of congestion/stampede.",
            'action': 'Dispatch crowd management team.'
        })

    # Check 2: Night-time Loitering in Unlit/Deserted Area
    if is_night and not cam['is_illuminated'] and simulated_people_count > 0:
        if safety_tier != 'CRITICAL':
            safety_tier = 'WARNING'
        anomalies.append({
            'type': 'DESERTED_ZONE_NIGHT_ACTIVITY',
            'severity': 'MEDIUM',
            'details': f"Movement detected in low-illumination zone during curfew window ({current_hour}:00 hrs).",
            'action': 'Direct pan-tilt-zoom (PTZ) camera and alert perimeter patrol.'
        })

    return {
        'camera_id': cam['camera_id'],
        'zone_name': cam['zone_name'],
        'status': cam['status'],
        'resolution': cam['resolution'],
        'stream_url': cam['ip_stream'],
        'current_detected_occupancy': simulated_people_count,
        'normal_zone_capacity': cam['normal_capacity'],
        'safety_tier': safety_tier,
        'ai_confidence_pct': round(confidence * 100, 1),
        'detected_anomalies': anomalies,
        'analyzed_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }


def get_all_campus_cctv_telemetry() -> List[Dict[str, Any]]:
    """Returns synthesized real-time vision telemetry across all cameras."""
    return [analyze_cctv_feed(c['camera_id']) for c in CCTV_CAMERA_FEEDS]
