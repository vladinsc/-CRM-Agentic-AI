from sqlalchemy import Column, Integer, String, DateTime, func, Float, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


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
    vector_embedding = Column(ARRAY(Float), nullable=True) # The learned array
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner = relationship("User", back_populates="personas")
    rules = relationship("UserIcpRule", back_populates="persona")

class UserIcpRule(Base):
    __tablename__ = "user_icp_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    criteria_field = Column(String, nullable=False)
    operator = Column(String, nullable=False)
    target_value = Column(String, nullable=False)
    point_value = Column(Integer, nullable=False)

    owner = relationship("User", back_populates="rules")
    persona = relationship("IcpPersona", back_populates="rules")