# AIModel, Product, GenerationJob, Content ORM 엔티티
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from .base import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


class AIModel(Base):
    __tablename__ = "ai_models"

    model_id = Column(String, primary_key=True, default=_uuid)
    soul_reference_id = Column(String, nullable=True)
    body_style = Column(String, nullable=True)
    hair_style = Column(String, nullable=True)
    age = Column(String, nullable=True)
    mood = Column(String, nullable=True)
    fashion_style = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class Product(Base):
    __tablename__ = "products"

    product_id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    color = Column(String, nullable=True)
    material = Column(String, nullable=True)
    silhouette = Column(String, nullable=True)
    season = Column(String, nullable=True)
    style = Column(String, nullable=True)
    target_customer = Column(String, nullable=True)
    image_ref = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    job_id = Column(String, primary_key=True, default=_uuid)
    type = Column(Enum("soul", "image", "video", name="job_type"), nullable=False)
    product_id = Column(String, ForeignKey("products.product_id"), nullable=True)
    model_id = Column(String, ForeignKey("ai_models.model_id"), nullable=True)
    status = Column(
        Enum("queued", "running", "done", "failed", name="job_status"),
        default="queued",
        nullable=False,
    )
    mcp_call_ref = Column(String, nullable=True)
    params = Column(JSON, nullable=True)
    result_refs = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class Content(Base):
    __tablename__ = "contents"

    content_id = Column(String, primary_key=True, default=_uuid)
    source_ref = Column(String, nullable=True)
    caption = Column(String, nullable=True)
    hashtags = Column(JSON, nullable=True)
    ad_copy = Column(String, nullable=True)
    channel = Column(String, nullable=True)
    status = Column(String, default="draft")
    created_at = Column(DateTime(timezone=True), default=_now)
