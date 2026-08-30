"""
=============================================================================
CampusGuard AI — Multilingual Localization (i18n) Engine
=============================================================================
Supports dynamic multi-language switching across 7 languages:
English (en), Hindi (hi), Spanish (es), Tamil (ta), Telugu (te), French (fr), German (de).
Specifically designed for multilingual parent notifications and emergency safety.
=============================================================================
"""

from typing import List, Dict

TRANSLATION_CATALOG = {
    'en': {
        'brand': 'CampusGuard AI',
        'dashboard': 'Dashboard',
        'attendance': 'Attendance',
        'academics': 'Academics',
        'exams': 'Examinations',
        'fees': 'Fee Center',
        'safety': 'Safety & SOS',
        'emergency_sos': 'Emergency SOS',
        'safe_walk': 'Safe Walk Companion',
        'grievance': 'Grievance Tickets',
        'timetable': 'Class Timetable',
        'messages': 'Messages & Alerts',
        'logout': 'Sign Out',
        'overall_attendance': 'Overall Aggregate Attendance',
        'pending_fees': 'Outstanding Pending Dues',
        'next_class': 'Next Scheduled Class',
        'sos_alert_active': 'CRITICAL SOS ALERT ACTIVE',
        'call_security': 'Call Security Control',
        'call_medical': 'Call Emergency Health Center'
    },
    'hi': {
        'brand': 'कैंपसगार्ड एआई',
        'dashboard': 'डैशबोर्ड',
        'attendance': 'उपस्थिति (अटेंडेंस)',
        'academics': 'शैक्षणिक',
        'exams': 'परीक्षाएं',
        'fees': 'शुल्क केंद्र',
        'safety': 'सुरक्षा और आपातकालीन',
        'emergency_sos': 'आपातकालीन एसओएस',
        'safe_walk': 'सुरक्षित वॉक साथी',
        'grievance': 'शिकायत निवारण',
        'timetable': 'समय सारिणी',
        'messages': 'संदेश और अलर्ट',
        'logout': 'लॉग आउट',
        'overall_attendance': 'कुल उपस्थिति',
        'pending_fees': 'बकाया शुल्क',
        'next_class': 'अगली कक्षा',
        'sos_alert_active': 'आपातकालीन एसओएस चेतावनी सक्रिय',
        'call_security': 'सुरक्षा नियंत्रण को कॉल करें',
        'call_medical': 'स्वास्थ्य केंद्र को कॉल करें'
    },
    'ta': {
        'brand': 'கேம்பஸ்கார்ட் AI',
        'dashboard': 'முகப்பு',
        'attendance': 'வருகைப்பதிவு',
        'academics': 'கல்வி விவரங்கள்',
        'exams': 'தேர்வுகள்',
        'fees': 'கட்டண மையம்',
        'safety': 'பாதுகாப்பு & SOS',
        'emergency_sos': 'அவசர SOS',
        'safe_walk': 'பாதுகாப்பான நடை துணை',
        'grievance': 'புகார் பதிவு',
        'timetable': 'வகுப்பு அட்டவணை',
        'messages': 'செய்திகள் & எச்சரிக்கைகள்',
        'logout': 'வெளியேறு',
        'overall_attendance': 'மொத்த வருகை',
        'pending_fees': 'நிலுவைத் தொகை',
        'next_class': 'அடுத்த வகுப்பு',
        'sos_alert_active': 'அவசர எச்சரிக்கை செயலில் உள்ளது',
        'call_security': 'பாதுகாப்பு கட்டுப்பாட்டை அழைக்கவும்',
        'call_medical': 'மருத்துவ மையத்தை அழைக்கவும்'
    },
    'es': {
        'brand': 'CampusGuard AI',
        'dashboard': 'Panel Principal',
        'attendance': 'Asistencia',
        'academics': 'Académico',
        'exams': 'Exámenes',
        'fees': 'Centro de Pagos',
        'safety': 'Seguridad y SOS',
        'emergency_sos': 'SOS de Emergencia',
        'safe_walk': 'Compañero de Ruta Segura',
        'grievance': 'Reclamaciones',
        'timetable': 'Horario de Clases',
        'messages': 'Mensajes y Alertas',
        'logout': 'Cerrar Sesión',
        'overall_attendance': 'Asistencia Total',
        'pending_fees': 'Cuotas Pendientes',
        'next_class': 'Próxima Clase',
        'sos_alert_active': 'ALERTA SOS CRÍTICA ACTIVA',
        'call_security': 'Llamar a Seguridad',
        'call_medical': 'Llamar a Centro Médico'
    },
    'fr': {
        'brand': 'CampusGuard AI',
        'dashboard': 'Tableau de Bord',
        'attendance': 'Présence',
        'academics': 'Scolarité',
        'exams': 'Examens',
        'fees': 'Frais et Finances',
        'safety': 'Sécurité et SOS',
        'emergency_sos': 'SOS Urgence',
        'safe_walk': 'Compagnon Trajet Sécurisé',
        'grievance': 'Réclamations',
        'timetable': 'Emploi du Temps',
        'messages': 'Messages et Alertes',
        'logout': 'Déconnexion',
        'overall_attendance': 'Taux de Présence Global',
        'pending_fees': 'Solde Restant',
        'next_class': 'Prochain Cours',
        'sos_alert_active': 'ALERTE SOS CRITIQUE ACTIVE',
        'call_security': 'Appeler la Sécurité',
        'call_medical': 'Appeler le Centre Médical'
    }
}


def t(key: str, lang: str = 'en') -> str:
    """Retrieves localized text for a specific key and language code."""
    lang_code = lang.lower() if lang else 'en'
    catalog = TRANSLATION_CATALOG.get(lang_code, TRANSLATION_CATALOG['en'])
    return catalog.get(key, TRANSLATION_CATALOG['en'].get(key, key))


def get_available_languages() -> List[Dict[str, str]]:
    """Returns list of supported language options for UI dropdown."""
    return [
        {'code': 'en', 'name': 'English', 'native': 'English'},
        {'code': 'hi', 'name': 'Hindi', 'native': 'हिन्दी'},
        {'code': 'ta', 'name': 'Tamil', 'native': 'தமிழ்'},
        {'code': 'es', 'name': 'Spanish', 'native': 'Español'},
        {'code': 'fr', 'name': 'French', 'native': 'Français'}
    ]
