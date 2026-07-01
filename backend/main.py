# JBLANC FastAPI 애플리케이션 진입점
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.product import router as product_router
from app.api.jobs import router as jobs_router
from app.api.ai import router as ai_router
from app.api.sns import router as sns_router
from app.api.pipeline import router as pipeline_router
from app.models.base import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="JBLANC AI Fashion API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(product_router)
app.include_router(jobs_router)
app.include_router(ai_router)
app.include_router(sns_router)
app.include_router(pipeline_router)
