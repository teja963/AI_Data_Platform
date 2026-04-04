from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from datetime import datetime
from core.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    module = Column(String)
    category = Column(String)
    difficulty = Column(String)
    # store raw JSON payload of the question for fidelity
    payload = Column(Text)
    # legacy fields for compatibility
    question = Column(Text)
    solution = Column(Text)


class Progress(Base):
    __tablename__ = "progress"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    question_id = Column(Integer)
    status = Column(String)  # solved / unsolved
    attempts = Column(Integer, default=0)


class InterviewRun(Base):
    __tablename__ = "interview_runs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    score = Column(Integer)
    accuracy = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)