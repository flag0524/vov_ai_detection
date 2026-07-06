# pytest 공용 픽스처: 인메모리 SQLite로 격리된 FastAPI TestClient 제공
import os
import sys

# backend/ 를 import 경로에 추가 (tests/ 하위에서 실행되므로)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from main import app
from app.models.base import Base, get_db


@pytest.fixture(autouse=True)
def force_stub_mode(monkeypatch):
    """테스트가 유료 외부 API(Higgsfield)를 호출하지 않도록 강제 스텁 모드.
    실생성 검증은 테스트 스위트가 아니라 의도된 수동 실행으로 수행한다.
    (Agent 2/5는 ADR-012로 규칙 기반 템플릿이 되어 외부 의존이 없다.)"""
    from agents import higgsfield_client as hf

    monkeypatch.setattr(hf, "API_KEY", "")
    monkeypatch.setattr(hf, "API_SECRET", "")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """테스트마다 새 인메모리 DB와 임시 스토리지를 쓰는 TestClient."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    # 업로드가 개발용 storage/ 를 오염시키지 않도록 임시 디렉터리로 교체
    import app.api.product as product_module
    monkeypatch.setattr(product_module, "STORAGE_DIR", str(tmp_path))

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
