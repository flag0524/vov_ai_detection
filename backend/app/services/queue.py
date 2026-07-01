# Redis 기반 RQ Job Queue 연결 및 enqueue 헬퍼
import os
import redis
from rq import Queue

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_conn = redis.from_url(_redis_url)
job_queue = Queue("jblanc", connection=_conn)


def enqueue(func, *args, **kwargs):
    """작업을 큐에 등록하고 RQ Job ID를 반환한다."""
    job = job_queue.enqueue(func, *args, **kwargs)
    return job.id
