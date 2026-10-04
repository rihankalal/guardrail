from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./audit_log.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    username = Column(String)
    role = Column(String)
    question = Column(Text)
    retrieved_source = Column(String, nullable=True)
    retrieved_classification = Column(String, nullable=True)
    access_denied = Column(Boolean, default=False)
    redacted_count = Column(Integer, default=0)
    guardrail_status = Column(String, nullable=True)
    answer_preview = Column(Text, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def log_query(
    username: str,
    role: str,
    question: str,
    retrieved_source: str = None,
    retrieved_classification: str = None,
    access_denied: bool = False,
    redacted_count: int = 0,
    guardrail_status: str = None,
    answer_preview: str = None,
):
    session = SessionLocal()
    try:
        entry = AuditLog(
            username=username,
            role=role,
            question=question,
            retrieved_source=retrieved_source,
            retrieved_classification=retrieved_classification,
            access_denied=access_denied,
            redacted_count=redacted_count,
            guardrail_status=guardrail_status,
            answer_preview=(answer_preview or "")[:200],
        )
        session.add(entry)
        session.commit()
    finally:
        session.close()


def get_blocked_count_for_user(username: str, minutes: int = 5) -> int:
    """Counts recent blocked attempts by this user — used for threshold flagging."""
    from datetime import timedelta
    session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        count = (
            session.query(AuditLog)
            .filter(AuditLog.username == username)
            .filter(AuditLog.access_denied == True)
            .filter(AuditLog.timestamp >= cutoff)
            .count()
        )
        return count
    finally:
        session.close()


def get_all_flagged_users(minutes: int = 5, threshold: int = 3):
    """Returns a list of (username, blocked_count) for anyone over the threshold recently."""
    from datetime import timedelta
    from sqlalchemy import func

    session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        results = (
            session.query(AuditLog.username, func.count(AuditLog.id).label("blocked_count"))
            .filter(AuditLog.access_denied == True)
            .filter(AuditLog.timestamp >= cutoff)
            .group_by(AuditLog.username)
            .having(func.count(AuditLog.id) >= threshold)
            .all()
        )
        return [{"username": r.username, "blocked_count": r.blocked_count} for r in results]
    finally:
        session.close()