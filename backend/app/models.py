from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin | user | viewer
    first_login = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    assignments = relationship("UserProject", back_populates="user", cascade="all, delete-orphan")
    calculations = relationship("Calculation", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    assignments = relationship("UserProject", back_populates="project", cascade="all, delete-orphan")
    calculations = relationship("Calculation", back_populates="project", cascade="all, delete-orphan")


class UserProject(Base):
    __tablename__ = "user_projects"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)

    user = relationship("User", back_populates="assignments")
    project = relationship("Project", back_populates="assignments")

    __table_args__ = (UniqueConstraint("user_id", "project_id", name="uq_user_project"),)


class Calculation(Base):
    __tablename__ = "calculations"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    material = Column(String, nullable=False)
    length = Column(Float, nullable=False)
    width = Column(Float, nullable=True)
    thickness = Column(Float, nullable=True)
    diameter = Column(Float, nullable=True)
    qty = Column(Integer, nullable=False)
    weight_kg = Column(Float, nullable=False)
    weight_tonnes = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="calculations")
    user = relationship("User", back_populates="calculations")
