from sqlalchemy import Column, Integer, String, DateTime, Text, Numeric, ForeignKey, func, BigInteger, Boolean, Float
from sqlalchemy.dialects.postgresql import JSONB
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
    is_verified = Column(Boolean, default=False)
    connected_accounts = relationship("ConnectedAccount", back_populates="owner")

class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False, default="google")  # ex: "google"
    email = Column(String, index=True)
    refresh_token = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_history_id = Column(BigInteger, nullable=True)
    is_watching = Column(Boolean, default=False)
    owner = relationship("User", back_populates="connected_accounts")

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    deal_value = Column(Numeric(precision=10, scale=2), nullable=True)
    currency = Column(String(10), default="EUR", nullable=False)
    last_activity_description = Column(Text, nullable=True)
    intent_score = Column(Integer, nullable=True)
    last_researched_at = Column(DateTime(timezone=True), nullable=True)
    signals = Column(JSONB, default=list, nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String, default="new", nullable=False)
    linkedin_url = Column(String, nullable=True)
    company_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    query = Column(Text, nullable=False)
    pages_requested = Column(Integer, nullable=False)
    status = Column(String, default="pending", nullable=False)
    scraped_count = Column(Integer, default=0, nullable=False)
    leads_created = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentActivity(Base):
    __tablename__ = "agent_activities"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    lead_name = Column(String, nullable=False)
    agent_name = Column(String, nullable=False)
    # action_type: "research" | "email" | "analysis" | "call" | "insight" — extensible
    action_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSONB, default=dict, nullable=False)
    status = Column(String, default="completed", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CopilotResult(Base):
    __tablename__ = "copilot_results"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), unique=True, nullable=False, index=True)
    winning_argument = Column(Text, nullable=True)
    draft_message = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    model_used = Column(String(100), nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    lead_snapshot = Column(JSONB, nullable=True)


class ICPBlueprint(Base):
    __tablename__ = "icp_blueprints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    raw_inputs = Column(JSONB, nullable=False)
    structured_data = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    email_id = Column(String, unique=True, index=True, nullable=False)
    subject = Column(String, nullable=False)
    s3_path = Column(String, nullable=False)
    ai_reasoning = Column(Text, nullable=True)
    classification_score = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
