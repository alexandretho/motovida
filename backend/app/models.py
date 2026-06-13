from datetime import datetime
from sqlalchemy import (Boolean, Column, DateTime, Enum, ForeignKey, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship
from .database import Base

PROFESSIONS = ("motoboy", "motociclista", "entregador", "familiar", "outro")
MEI_STATUSES = ("ja_sou_mei", "quero_abrir_mei", "preciso_regularizar", "nao_sei_informar")
REQUEST_TYPES = ("social", "juridico", "psicologico", "administrativo", "mei", "outro")
PRIORITIES = ("baixa", "media", "alta", "urgente")
STATUSES = ("aberta", "em_analise", "em_atendimento", "concluida", "cancelada")
LEGAL_CATEGORIES = ("acidente_transito", "trabalhista", "previdenciaria", "orientacao_geral")
PSY_RELATIONS = ("vitima_acidente", "familiar_vitima", "outro")
MEI_TOPICS = ("abertura", "regularizacao", "duvida_geral", "outro")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(180), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum("admin", "affiliate", name="user_role"), nullable=False, default="affiliate")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    affiliate = relationship("Affiliate", back_populates="user", uselist=False)


class Affiliate(Base):
    __tablename__ = "affiliates"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    full_name = Column(String(180), nullable=False)
    cpf = Column(String(11), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    whatsapp = Column(String(20), nullable=False)
    email = Column(String(180), nullable=False)
    city = Column(String(120), nullable=False, index=True)
    state = Column(String(2), nullable=False, index=True)
    profession = Column(Enum(*PROFESSIONS, name="profession"), nullable=False)
    mei_status = Column(Enum(*MEI_STATUSES, name="mei_status"), nullable=False)
    support_needs = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="affiliate")
    consents = relationship("LgpdConsent", back_populates="affiliate")
    requests = relationship("SupportRequest", back_populates="affiliate")
    enrollments = relationship("CourseEnrollment", back_populates="affiliate")
    attendances = relationship("Attendance", back_populates="affiliate")


class LgpdConsent(Base):
    __tablename__ = "lgpd_consents"
    id = Column(Integer, primary_key=True)
    affiliate_id = Column(Integer, ForeignKey("affiliates.id"), nullable=False)
    accepted = Column(Boolean, nullable=False, default=True)
    policy_version = Column(String(10), nullable=False)
    accepted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    affiliate = relationship("Affiliate", back_populates="consents")


class SupportRequest(Base):
    __tablename__ = "support_requests"
    id = Column(Integer, primary_key=True)
    affiliate_id = Column(Integer, ForeignKey("affiliates.id"), nullable=False)
    type = Column(Enum(*REQUEST_TYPES, name="request_type"), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(Enum(*PRIORITIES, name="priority"), nullable=False, default="media")
    status = Column(Enum(*STATUSES, name="status"), nullable=False, default="aberta")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    affiliate = relationship("Affiliate", back_populates="requests")
    history = relationship("RequestHistory", back_populates="request", order_by="RequestHistory.created_at")


class RequestHistory(Base):
    __tablename__ = "request_history"
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("support_requests.id"), nullable=False)
    old_status = Column(String(20))
    new_status = Column(String(20))
    note = Column(Text)
    author = Column(String(180))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    request = relationship("SupportRequest", back_populates="history")


class LegalSupport(Base):
    __tablename__ = "legal_support"
    id = Column(Integer, primary_key=True)
    affiliate_id = Column(Integer, ForeignKey("affiliates.id"), nullable=False)
    category = Column(Enum(*LEGAL_CATEGORIES, name="legal_category"), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(*STATUSES, name="legal_status"), nullable=False, default="aberta")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    affiliate = relationship("Affiliate")


class PsychologicalSupport(Base):
    __tablename__ = "psychological_support"
    id = Column(Integer, primary_key=True)
    affiliate_id = Column(Integer, ForeignKey("affiliates.id"), nullable=False)
    relation = Column(Enum(*PSY_RELATIONS, name="psy_relation"), nullable=False)
    preferred_date = Column(String(60))
    description = Column(Text, nullable=False)
    status = Column(Enum(*STATUSES, name="psy_status"), nullable=False, default="aberta")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    affiliate = relationship("Affiliate")


class MeiSupport(Base):
    __tablename__ = "mei_support"
    id = Column(Integer, primary_key=True)
    affiliate_id = Column(Integer, ForeignKey("affiliates.id"), nullable=False)
    topic = Column(Enum(*MEI_TOPICS, name="mei_topic"), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(*STATUSES, name="mei_req_status"), nullable=False, default="aberta")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    affiliate = relationship("Affiliate")


class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(120), nullable=False)
    workload_hours = Column(Integer, default=0)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    enrollments = relationship("CourseEnrollment", back_populates="course")


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (UniqueConstraint("course_id", "affiliate_id", name="uq_course_affiliate"),)
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    affiliate_id = Column(Integer, ForeignKey("affiliates.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    course = relationship("Course", back_populates="enrollments")
    affiliate = relationship("Affiliate", back_populates="enrollments")


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    title = Column(String(180), nullable=False)
    description = Column(Text)
    event_date = Column(DateTime)
    location = Column(String(180))
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Partner(Base):
    __tablename__ = "partners"
    id = Column(Integer, primary_key=True)
    name = Column(String(180), nullable=False)
    category = Column(String(120), nullable=False, index=True)
    discount = Column(String(120))
    city = Column(String(120))
    state = Column(String(2))
    contact = Column(String(180))
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Attendance(Base):
    __tablename__ = "attendances"
    id = Column(Integer, primary_key=True)
    affiliate_id = Column(Integer, ForeignKey("affiliates.id"), nullable=False)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    affiliate = relationship("Affiliate", back_populates="attendances")
    admin = relationship("User")
