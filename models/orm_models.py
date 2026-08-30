from .base import db_orm
from datetime import datetime

class Student(db_orm.Model):
    __tablename__ = 'students'
    id = db_orm.Column(db_orm.Integer, primary_key=True, autoincrement=True)
    name = db_orm.Column(db_orm.String, nullable=False)
    register_number = db_orm.Column(db_orm.String, unique=True, nullable=False)
    email = db_orm.Column(db_orm.String, nullable=False)
    password_hash = db_orm.Column(db_orm.String, nullable=False)
    department = db_orm.Column(db_orm.String, nullable=False)
    year = db_orm.Column(db_orm.Integer, nullable=False)
    program = db_orm.Column(db_orm.String, default='B.Tech')
    semester = db_orm.Column(db_orm.Integer, default=1)
    section = db_orm.Column(db_orm.String, default='A')
    phone = db_orm.Column(db_orm.String, default='')
    status = db_orm.Column(db_orm.String, default='ACTIVE')
    created_at = db_orm.Column(db_orm.DateTime, default=datetime.utcnow)
    # Note: Only a partial mapping is included to demonstrate the foundation.
    # We will expand this during incremental migration.
