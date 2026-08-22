"""
CampusGuard AI — Domain Models & Data Access Objects
"""

from .user import StudentModel, ParentModel, FacultyModel, AdminModel
from .academic import CourseModel, TimetableModel, StudyMaterialModel
from .attendance import AttendanceModel
from .examination import ExaminationModel, MarksModel
from .assignment import AssignmentModel
from .fee import FeeModel, PaymentTransactionModel
from .leave import HostelModel, HostelLeaveModel, StudentRequestModel
from .communication import AnnouncementModel, MessageModel, NotificationModel, AlertModel
from .complaint import ComplaintModel
from .safety import IncidentModel, EmergencyContactModel, SafeWalkModel
from .audit import AuditLogModel, SystemSettingModel
