from sqlalchemy import Column, Integer, String, DateTime, func, Float, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from app.database import Base
from pgvector.sqlalchemy import Vector

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="sales_rep", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    latest_login_at = Column(DateTime(timezone=True), nullable=True)

    personas = relationship("IcpPersona", back_populates="owner")
    rules = relationship("UserIcpRule", back_populates="owner")


class IcpPersona(Base):
    __tablename__ = "icp_personas"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False) # The natural language prompt
    vector_embedding = Column(Vector(384), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner = relationship("User", back_populates="personas")
    rules = relationship("UserIcpRule", back_populates="persona")

class UserIcpRule(Base):
    __tablename__ = "user_icp_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    persona_id = Column(Integer, ForeignKey("icp_personas.id"), nullable=True)
    criteria_field = Column(String, nullable=False)
    operator = Column(String, nullable=False)
    target_value = Column(String, nullable=False)
    point_value = Column(Integer, nullable=False)

    owner = relationship("User", back_populates="rules")
    persona = relationship("IcpPersona", back_populates="rules")

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="clients")
    projects = relationship("Project", back_populates="client", cascade="all, delete-orphan")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name = Column(String, nullable=False)
    
    # JSONB allows you to store flexible dictionaries: {"budget": 5000, "urgency": "High"}
    attributes = Column(JSONB, nullable=True, default={})
    
    # Stores an array of message dictionaries: [{"sender": "client", "text": "..."}, ...]
    conversation_history = Column(JSONB, nullable=True, default=[])

    vector_embedding = Column(Vector(384), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    client = relationship("Client", back_populates="projects")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    sender_role = Column(String, nullable=False) 
    s3_file_path = Column(String, nullable=False) # Adaugam asta ca sa fim siguri
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    project = relationship("Project", back_populates="messages")