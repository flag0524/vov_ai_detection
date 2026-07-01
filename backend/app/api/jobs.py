# 비동기 작업 상태 조회 라우터
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.entities import GenerationJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).filter(GenerationJob.job_id == job_id).first()
    if not job:
        return {"error": "not found"}
    return {
        "job_id": job.job_id,
        "type": job.type,
        "status": job.status,
        "result_refs": job.result_refs,
    }
