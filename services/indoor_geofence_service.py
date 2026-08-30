"""
=============================================================================
CampusGuard AI — Indoor Geolocation & BLE Beacon Telemetry Resolver
=============================================================================
Maps raw GPS coordinates, Wi-Fi BSSIDs, and BLE Beacon identifiers to exact
multi-story campus indoor micro-locations:
- Building Wing, Floor Level, and Room Identifier
- Nearest Emergency Exit & Evacuation Stairwell
- Nearest Fixed Security Outpost & First-Aid Station
- Real-time Zone Risk Factor correlation
=============================================================================
"""

import math
from typing import Dict, Any, Optional

# Campus Geofenced Indoor Zones Repository
CAMPUS_INDOOR_ZONES = [
    {
        "zone_id": "ZONE_ENG_B_FL3",
        "building": "Engineering Academic Block B",
        "wing": "Oak Wing (North)",
        "floor": "3rd Floor",
        "room_range": "301 - 325",
        "gps_bounds": {"lat_min": 12.9710, "lat_max": 12.9730, "lon_min": 77.5940, "lon_max": 77.5960},
        "beacons": ["BCN-ENG-301", "BCN-ENG-304", "BCN-ENG-312"],
        "nearest_exit": "North Stairwell Exit 3B (15 meters)",
        "nearest_security_post": "Gate 2 Security Booth (120m)",
        "nearest_first_aid": "Block B 2nd Floor First Aid Station",
        "active_cctv_ids": ["CAM-B-301", "CAM-B-304"]
    },
    {
        "zone_id": "ZONE_HOSTEL_B_FL2",
        "building": "Hostel Block B (Men's Residence)",
        "wing": "South Wing",
        "floor": "2nd Floor",
        "room_range": "201 - 240",
        "gps_bounds": {"lat_min": 12.9735, "lat_max": 12.9755, "lon_min": 77.5965, "lon_max": 77.5985},
        "beacons": ["BCN-HST-204", "BCN-HST-210"],
        "nearest_exit": "South Fire Escape Stairwell (10 meters)",
        "nearest_security_post": "Hostel B Warden Guard Desk (Ground Floor)",
        "nearest_first_aid": "Hostel Medical Kit (Warden Office)",
        "active_cctv_ids": ["CAM-HST-201", "CAM-HST-202"]
    },
    {
        "zone_id": "ZONE_CENTRAL_LIB_FL1",
        "building": "Central University Library",
        "wing": "East Wing",
        "floor": "1st Floor (Reading Hall)",
        "room_range": "Main Reading Hall",
        "gps_bounds": {"lat_min": 12.9690, "lat_max": 12.9705, "lon_min": 77.5920, "lon_max": 77.5935},
        "beacons": ["BCN-LIB-101", "BCN-LIB-102"],
        "nearest_exit": "Main Library Quadrangle Entrance (25 meters)",
        "nearest_security_post": "Library Turnstile Security Desk",
        "nearest_first_aid": "Library Reception First Aid Kit",
        "active_cctv_ids": ["CAM-LIB-01", "CAM-LIB-02"]
    },
    {
        "zone_id": "ZONE_SPORTS_COMPLEX",
        "building": "Campus Indoor Sports Complex",
        "wing": "Arena Wing",
        "floor": "Ground Floor",
        "room_range": "Badminton & Gymnasium",
        "gps_bounds": {"lat_min": 12.9760, "lat_max": 12.9780, "lon_min": 77.5990, "lon_max": 77.6010},
        "beacons": ["BCN-SPT-01", "BCN-SPT-02"],
        "nearest_exit": "Main Arena Double Doors",
        "nearest_security_post": "Sports Complex Gate Station",
        "nearest_first_aid": "Sports Injury & Physiotherapy Room",
        "active_cctv_ids": ["CAM-SPT-01"]
    }
]


def resolve_indoor_location(
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    beacon_id: Optional[str] = None,
    zone_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolves exact micro-location from GPS coordinates, Beacon ID, or text hints.
    """
    # 1. Match by Beacon ID
    if beacon_id:
        for z in CAMPUS_INDOOR_ZONES:
            if beacon_id.upper() in [b.upper() for b in z['beacons']]:
                return {
                    'resolved': True,
                    'method': 'BLE_BEACON_TRIANGULATION',
                    'zone_id': z['zone_id'],
                    'building': z['building'],
                    'wing': z['wing'],
                    'floor': z['floor'],
                    'room_range': z['room_range'],
                    'nearest_exit': z['nearest_exit'],
                    'nearest_security_post': z['nearest_security_post'],
                    'nearest_first_aid': z['nearest_first_aid'],
                    'cctv_coverage': z['active_cctv_ids'],
                    'location_label': f"{z['building']}, {z['wing']} ({z['floor']})"
                }

    # 2. Match by GPS Bounds
    if latitude is not None and longitude is not None:
        for z in CAMPUS_INDOOR_ZONES:
            b = z['gps_bounds']
            if b['lat_min'] <= latitude <= b['lat_max'] and b['lon_min'] <= longitude <= b['lon_max']:
                return {
                    'resolved': True,
                    'method': 'GPS_GEOFENCE_RESOLVER',
                    'zone_id': z['zone_id'],
                    'building': z['building'],
                    'wing': z['wing'],
                    'floor': z['floor'],
                    'room_range': z['room_range'],
                    'nearest_exit': z['nearest_exit'],
                    'nearest_security_post': z['nearest_security_post'],
                    'nearest_first_aid': z['nearest_first_aid'],
                    'cctv_coverage': z['active_cctv_ids'],
                    'location_label': f"{z['building']}, {z['floor']}"
                }

    # 3. Match by Text Hint (e.g., "Block B", "Library")
    if zone_hint:
        hint_lower = zone_hint.lower()
        for z in CAMPUS_INDOOR_ZONES:
            if any(k in hint_lower for k in [z['building'].lower(), z['wing'].lower(), z['zone_id'].lower()]):
                return {
                    'resolved': True,
                    'method': 'SEMANTIC_ZONE_HINT',
                    'zone_id': z['zone_id'],
                    'building': z['building'],
                    'wing': z['wing'],
                    'floor': z['floor'],
                    'room_range': z['room_range'],
                    'nearest_exit': z['nearest_exit'],
                    'nearest_security_post': z['nearest_security_post'],
                    'nearest_first_aid': z['nearest_first_aid'],
                    'cctv_coverage': z['active_cctv_ids'],
                    'location_label': f"{z['building']} ({z['wing']})"
                }

    # Fallback to default campus central coordinates
    return {
        'resolved': False,
        'method': 'CAMPUS_DEFAULT_EXTERIOR',
        'zone_id': 'CAMPUS_OUTDOOR_GENERIC',
        'building': 'Main Campus Quadrangle',
        'wing': 'Central Perimeter',
        'floor': 'Ground Level',
        'room_range': 'Outdoor Pathway',
        'nearest_exit': 'Main Institutional Campus Gate (South)',
        'nearest_security_post': 'Central Security Control Tower',
        'nearest_first_aid': 'Campus Health Pavilion',
        'cctv_coverage': ['CAM-OUTDOOR-MAIN-01'],
        'location_label': 'Campus Main Grounds'
    }
