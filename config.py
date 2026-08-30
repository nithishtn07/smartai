import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

try:
    from dotenv import load_dotenv
    env_file = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_file):
        load_dotenv(env_file)
except ImportError:
    pass

class BaseConfig:
    SECRET_KEY = os.environ.get(
        'CAMPUSGUARD_SECRET_KEY', 
        'campusguard-ai-secure-secret-key-2026-smart-safe-campus'
    )
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    DATABASE_PATH = os.path.join(BASE_DIR, 'database.db')
    DATABASE_URL = os.environ.get('DATABASE_URL', f"sqlite:///{DATABASE_PATH}")
    ATTENDANCE_THRESHOLD = float(os.environ.get('CAMPUSGUARD_ATTENDANCE_THRESHOLD', 75.0))
    INSTITUTION_NAME = os.environ.get('INSTITUTION_NAME', 'CampusGuard Institute of Science & Technology')
    ACADEMIC_YEAR = os.environ.get('ACADEMIC_YEAR', '2026-2027')
    ACTIVE_SEMESTER = os.environ.get('ACTIVE_SEMESTER', 'Fall 2026 (Semester 5)')
    TESTING = False
    DEBUG = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    # Require strong secret key in production
    SECRET_KEY = os.environ.get('CAMPUSGUARD_SECRET_KEY')


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SECRET_KEY = 'test-secret-key-campusguard'


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    env = os.environ.get('FLASK_ENV', 'development').lower()
    config = config_by_name.get(env, DevelopmentConfig)
    if env == 'production' and not config.SECRET_KEY:
        raise RuntimeError("CAMPUSGUARD_SECRET_KEY environment variable is required in production.")
    return config
