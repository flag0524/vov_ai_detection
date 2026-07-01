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
- [ ] 디렉터리 스캐폴딩 (frontend, backend, agents, workers)
- [ ] FastAPI 스켈레톤 + 헬스체크 엔드포인트
- [ ] PostgreSQL 연결 + 스키마 초기화 (AIModel, Product, GenerationJob, Content)
- [ ] Redis + Job Queue 연결
- [ ] Object Storage 연결 + 업로드 더미 테스트
- [ ] 검증 → tests.md Phase 0

### Phase 1 — 상품 분석 & AI 모델 생성
- [ ] Agent 1: 상품 이미지 Vision 분석 → 메타데이터 추출 (category, color, material 등)
- [ ] POST /product/upload API 구현
- [ ] Agent 3: `higgsfield-soul-id` 호출 → `soul_reference_id` DB 저장
- [ ] POST /ai/model/create API 구현
- [ ] 검증 → tests.md Phase 1

### Phase 2 — 상품 원본 유지 이미지 생성
- [ ] Agent 2: 프롬프트 자동 생성 (상품 메타 + 모델 속성 → 프롬프트)
- [ ] Agent 3: `higgsfield-product-photoshoot` / `higgsfield-generate` 호출
- [ ] POST /ai/image/generate API + 비동기 job_id 추적
- [ ] 상품 원본 유지율 검수 (SSIM/임베딩) + 미달 재생성 큐 연결
- [ ] 검증 → tests.md Phase 2

### Phase 3 — 영상 생성
- [ ] Agent 4: `higgsfield-generate` (image-to-video, 5~15초, 9:16)
- [ ] POST /ai/video/generate API 구현
- [ ] 카메라 워킹·모션 옵션 파라미터화
- [ ] 검증 → tests.md Phase 3

### Phase 4 — SNS 콘텐츠 자동 생성
- [ ] Agent 5: 게시글 문구 + 해시태그 + 광고 카피 생성
- [ ] POST /sns/content/create API 구현
- [ ] 검증 → tests.md Phase 4

### Phase 5 — 프론트엔드 & 오케스트레이션
- [ ] Next.js: 상품 업로드 → 생성 요청 → 결과 확인 → 다운로드 → SNS 예약 화면
- [ ] MCP Orchestrator: Agent 1~5 end-to-end 파이프라인 연결
- [ ] GET /jobs/{job_id} 상태 폴링 UI 연결
- [ ] 검증 → tests.md Phase 5

### Phase 6 — 품질 검증 자동화 & 안정화
- [ ] Image/Video Quality Score 자동 평가 루프
- [ ] 기준 미달 → 재생성 큐 자동 회송 완성
- [ ] 브랜드 스타일 학습 (JBLANC STYLE MODEL)
- [ ] 검증 → tests.md Phase 6

## 의사결정 확정 (2026-06-30)

- [x] Object Storage: 로컬 파일 시스템 (Phase 0), 이후 S3 전환
- [x] Vector DB: pgvector (PostgreSQL 내장)
- [x] 개발 환경: 로컬 직접 설치 (Docker 없음)
- [x] Higgsfield MCP 토큰: 없음 → Phase 0 완료 후 토큰 확보 시 Phase 1 진행
