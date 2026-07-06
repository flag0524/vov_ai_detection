# plan.md — JBLANC 구현 계획

> 단계별 실행 계획. 각 Phase 완료 시 tests.md의 검증 기준을 충족해야 다음 단계로 진행.

---

## 아키텍처 결정 (불변)

| 결정 | 내용 |
| --- | --- |
| 생성 인프라 | Higgsfield MCP (자체 Diffusion 없음) |
| 호출 주체 | Agent가 직접 MCP 호출 (FastAPI는 위임만) |
| 모델 일관성 | Soul ID (`higgsfield-soul-id` → `soul_reference_id` 저장) |

## 스택

- Frontend: Next.js (App Router, TypeScript)
- Backend: FastAPI (Python, Pydantic)
- 비동기: Celery/RQ + Redis
- DB: PostgreSQL (메타) + pgvector/Qdrant (검수 임베딩)
- Storage: S3 호환 Object Storage
- Agent: MCP Agent 1~5

## 디렉터리 구조

```
vov_ai_detection/
├── docs/
├── frontend/
├── backend/
│   ├── app/api/          # product / ai / sns 라우터
│   ├── app/services/     # 파이프라인·스토리지·큐
│   └── app/models/       # ORM 엔티티
├── agents/               # Agent 1~5 (Higgsfield MCP 호출)
└── workers/              # 비동기 워커
```

## Phase별 작업

### Phase 0 — 기반 셋업
- [x] 디렉터리 스캐폴딩 (frontend, backend, agents, workers)
- [x] FastAPI 스켈레톤 + 헬스체크 엔드포인트
- [x] DB 연결 + 스키마 초기화 (AIModel, Product, GenerationJob, Content) — 개발은 SQLite, PostgreSQL은 운영 전환 시
- [ ] Redis + Job Queue 연결 — 보류 (이 머신에 설치 인프라 없음, 동기 처리 중. 2026-07-01 사용자 승인)
- [x] Object Storage 연결 + 업로드 더미 테스트 (로컬 파일시스템)
- [x] 검증 → tests.md Phase 0

### Phase 1 — 상품 분석 & AI 모델 생성
- [x] Agent 1: 상품 이미지 Vision 분석 → 메타데이터 추출 (category, color, material 등) — ANTHROPIC_API_KEY 없을 시 스텁 fallback
- [x] POST /product/upload API 구현
- [x] Agent 3: Soul ID → `soul_reference_id` DB 저장 — Soul 학습 API 미공개로 `create_soul_id()`는 스텁 유지 (프롬프트 고정 토큰으로 일관성 대체, API 공개 시 함수 교체)
- [x] POST /ai/model/create API 구현
- [x] 검증 → tests.md Phase 1 (스텁 모드 한정)
- [ ] 실생성물 재검증 — 선결: Higgsfield 크레딧 충전 (연동 코드·인증은 완료)

### Phase 2 — 상품 원본 유지 이미지 생성
- [x] Agent 2: 프롬프트 자동 생성 (상품 메타 + 모델 속성 → 프롬프트) — 스텁 fallback 포함
- [x] Agent 3: Higgsfield Platform REST 실연동 (`higgsfield-ai/soul/standard`, `agents/higgsfield_client.py`) — 인증 검증 완료, 크레딧 부족 시 스텁 강등
- [x] POST /ai/image/generate API 구현 (동기 처리, job_id는 DB 기록용)
- [x] 상품 원본 유지율 검수 (SSIM) 실계산 활성화 + 미달 시 동기 재생성 루프 (`run_with_quality_gate`, 최대 2회)
- [x] 검증 → tests.md Phase 2 (SSIM 실계산 확인, 이미지 자체는 스텁)
- [ ] 실이미지 기준 SSIM 재검증 — 선결: Higgsfield 크레딧 충전

### Phase 3 — 영상 생성
- [x] Agent 4: Higgsfield Platform REST 실연동 (`higgsfield-ai/dop/preview`, image-to-video 5~15초) — 크레딧 부족 시 스텁 강등
- [x] POST /ai/video/generate API 구현
- [x] 카메라 워킹·모션 옵션 파라미터화 (`camera_motion` → 영상 프롬프트 매핑)
- [x] 검증 → tests.md Phase 3 (스텁 모드 한정)
- [ ] 실영상 기준 얼굴 일관성/배경 왜곡 재검증 — 선결: Higgsfield 크레딧 충전

### Phase 4 — SNS 콘텐츠 자동 생성
- [x] Agent 5: 게시글 문구 + 해시태그 + 광고 카피 생성 — 스텁 fallback 포함
- [x] POST /sns/content/create API 구현
- [x] 검증 → tests.md Phase 4 (스텁 모드 한정, 실키 연결 시 실카피 재검증 필요)

### Phase 5 — 프론트엔드 & 오케스트레이션
- [x] Next.js: 상품 업로드 → 생성 요청 → 결과 확인 화면 (`/pipeline/run` 동기 호출 방식, 다운로드·SNS 예약 화면은 미구현)
- [x] MCP Orchestrator: Agent 1~5 end-to-end 파이프라인 연결 (`agents/orchestrator.py`, `backend/app/api/pipeline.py`)
- [x] 검증 → tests.md Phase 5 (curl CORS 검증 + 2026-07-03 실브라우저 클릭 E2E: 업로드→생성→화보/영상/SNS 카피 렌더링 확인)
- [ ] GET /jobs/{job_id} 상태 폴링 UI 연결 — 현재 파이프라인이 동기 처리라 폴링 불필요, Redis 도입 후 비동기 전환 시 추가
- [ ] 다운로드, SNS 예약 등록 화면 — Phase 5 후속 작업으로 보류

### Phase 6 — 품질 검증 자동화 & 안정화
- [x] Image/Video Quality Score 자동 평가 루프 — `run_with_quality_gate()`로 구현, `GenerationJob.result_refs`에 quality/attempts 기록
- [x] 기준 미달 → 재생성 큐 자동 회송 — 큐(Redis) 없이 동기 재시도(최대 2회)로 구현, 실패 시 job status="failed" 기록
- [x] 처리 시간 측정 — `processing_time_sec`을 `/pipeline/run` 응답에 기록
- [x] 검증 → tests.md Phase 6 (재시도/실패 시나리오는 mock으로 단위 검증, 실생성물 기준 재검증은 Higgsfield 연동 후)
- [ ] 브랜드 스타일 학습 (JBLANC STYLE MODEL) — Phase 2/3 실생성물 축적 후 착수

## 의사결정 확정 (2026-06-30)

- [x] Object Storage: 로컬 파일 시스템 (Phase 0), 이후 S3 전환
- [x] Vector DB: pgvector (PostgreSQL 내장)
- [x] 개발 환경: 로컬 직접 설치 (Docker 없음)
- [x] Higgsfield MCP 토큰: 없음 → Phase 0 완료 후 토큰 확보 시 Phase 1 진행

## 의사결정 확정 (2026-07-01)

- [x] Agent 1/2/5(Anthropic 호출)에도 Agent 3/4와 동일하게 실키 없으면 스텁 fallback 반환 — 키 없이도 E2E 파이프라인 전체를 항상 실행/검증 가능하게 유지
- [x] Higgsfield MCP 실연동: 이번 세션 보류. `claude.ai` 커넥터 OAuth 인증은 비대화형 세션에서 수행 불가 → 사용자가 claude.ai 커넥터 설정에서 먼저 인증 완료 후 재요청
- [x] Redis: 이번 세션 보류. 이 개발 머신에 native redis-server/choco/scoop/WSL 배포판이 전혀 없어 설치 자체가 환경 변경. 현재 규모는 동기 처리로 충분 → 스케일 필요 시점에 WSL 또는 Memurai로 도입
- [x] scikit-image/opencv-python-headless 설치, SSIM 실계산 활성화 (품질 게이트 실동작)
