import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Text, JSON, Integer, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

Base = declarative_base()
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    task_type = Column(String(20), default="analysis")  # analysis / dpr
    status = Column(String(20), default="pending")  # pending/running/success/failed
    current_step = Column(String(50), default="")
    progress = Column(Float, default=0.0)
    params = Column(JSON, default=dict)
    ref_file = Column(String(255), default="")
    upload_dir = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    csv_path = Column(String(500), nullable=True)


class MolecularDatabase(Base):
    __tablename__ = "molecular_databases"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, default="")
    formula_count = Column(Integer, default=0)
    file_count = Column(Integer, default=0)
    formulas = Column(JSON, default=list)
    files = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
