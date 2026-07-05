# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

JBLANC AI Fashion Marketing Automation System. 제이블랑(JBLANC) 패션 상품 이미지를 업로드하면 AI 모델 화보 이미지·릴스 영상·SNS 카피를 자동 생성하는 마케팅 자동화 플랫폼이다.

현재 상태는 **Phase 0~6 전체가 스텁 모드로 1회전 완료**다 (2026-07-01). E2E 파이프라인(`/pipeline/run`: 상품분석→모델생성→프롬프트→이미지→SSIM검증(+미달 시 자동 재생성 최대 2회)→영상→SNS카피)이 Next.js 프론트엔드(`frontend/`)에서 백엔드까지 CORS 포함 정상 동작한다. Higgsfield MCP(Agent 3/4 실호출)는 `claude.ai` 커넥터 인증 대기 중이며, Redis는 개발 머신에 설치 인프라가 없어 보류 상태(동기 처리 중)다 — 이 두 가지가 풀리면 Phase 2/3/6의 게이트를 실생성물 기준으로 재검증해야 한다. 작업 전 반드시 아래 문서들을 읽고 정렬 상태를 유지할 것.

- [docs/PRD.md](docs/PRD.md) — 제품 요구사항(기능·플로우·KPI).
- [docs/TRD.md](docs/TRD.md) — 기술 요구사항(아키텍처·API·데이터 모델). **최신 버전 v2.0 기준.**
- [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) — 개발 로드맵. **v2.0: 실구현 현황 + 2트랙(실연동 재검증/기능 완성) 체계.**
- [docs/ADR.md](docs/ADR.md) — 아키텍처 의사결정 기록 (ADR-001~010). 결정을 뒤집기 전 반드시 확인.
- [docs/TDD.md](docs/TDD.md) — 실구현 기준 기술 설계서 (컴포넌트·스키마·API·게이트·테스트 설계).
- [docs/SCREEN_DESIGN.md](docs/SCREEN_DESIGN.md) — 화면설계서 (SCR-001 구현 화면 + SCR-002~004 계획 화면, 와이어프레임·API 매핑).
- [docs/plan.md](docs/plan.md) — Phase별 실행 계획 및 체크리스트.
- [docs/status.md](docs/status.md) — 진행 현황(Phase 완료 여부·확정 의사결정). **작업 시작 전 항상 최신 상태 확인.**
- [docs/tests.md](docs/tests.md) — Phase별 검증 기준.
- [docs/goal.md](docs/goal.md) — 프로젝트 목표.

## 핵심 아키텍처 결정 (문서 전반에 걸친 big picture)

이 세 가지는 세 문서에 일관되게 깔린 전제이며, 코드도 여기에 맞춰야 한다.

1. **이미지/영상 생성 = Higgsfield MCP.** 자체 Diffusion / IP Adapter / ControlNet 추론 인프라는 쓰지 않는다. 생성은 전부 Higgsfield MCP 호출로 처리한다.
2. **에이전트가 MCP를 직접 호출.** FastAPI 백엔드는 Higgsfield를 직접 부르지 않는다. 백엔드는 작업(job)을 MCP Agent에 위임하고, 비동기 오케스트레이션·상태 관리만 담당한다.
3. **모델 얼굴 일관성 = Soul ID.** `higgsfield-soul-id`로 모델당 1회 Soul Character를 학습해 `soul_reference_id`를 저장하고, 모든 이미지·영상 생성에 동일 Soul ID를 주입한다. (구 `face_embedding` 개념은 폐기. 단 생성물 동일성 점수 계산용 검수 임베딩은 별도 보관.)

### 파이프라인 흐름

```
상품 업로드 → 상품 분석(Agent1) → 프롬프트 생성(Agent2)
 → 모델/이미지 생성(Agent3, Soul ID) → 영상 변환(Agent4)
 → SNS 카피(Agent5) → 인스타 등록 준비
```

### MCP Agent ↔ Higgsfield 기능 매핑

| Agent | 역할 | Higgsfield 호출 |
| --- | --- | --- |
| Agent 1 상품 분석 | 카테고리·속성 추출 | (Vision, 미사용) |
| Agent 2 Prompt Engineer | 프롬프트 자동 작성 | — |
| Agent 3 Fashion Model | 모델 학습·이미지 생성 | `higgsfield-soul-id`, `higgsfield-generate`, `higgsfield-product-photoshoot` |
| Agent 4 Video Creator | 이미지→영상 | `higgsfield-generate` (image-to-video) |
| Agent 5 Marketing | 문구·해시태그·카피 | — |

### 스택 / 디렉터리 현황

- Frontend: Next.js 16.2.9 (App Router, TS, Tailwind) — `frontend/`, 업로드→생성→결과 확인 단일 화면(`app/page.tsx`) 동작 중. 스캐폴딩이 자동 생성한 `frontend/CLAUDE.md`/`AGENTS.md`는 최신 Next.js 공식 컨벤션(에이전트에게 번들 문서 참고를 안내)이니 그대로 둘 것
- Backend: FastAPI (Python, Pydantic) — `backend/` — 헬스체크·상품 업로드/조회·AI·SNS·파이프라인 API 동작 중
- DB: SQLite(`backend/jblanc.db`, 개발) → PostgreSQL(운영) 전환 예정, 4개 테이블 ORM 구성 완료
- Storage: 로컬 파일시스템 — `storage/uploads/`, `storage/results/` → S3 전환 예정
- Vector DB: pgvector 예정 (Phase 2+, 검수 임베딩용)
- 품질 검증: `backend/app/services/quality.py` — scikit-image 기반 SSIM 실계산 (얼굴 유사도는 임베딩 입력 시에만 계산)
- 비동기: Celery/RQ + Redis Job Queue — `workers/`, `backend/app/services/queue.py` (패키지만 설치, 실연결 보류 — 이 머신에 redis-server/WSL 인프라 없음, 현재는 동기 처리)
- Agents: `agents/` — Agent 1(상품분석)/2(프롬프트)/5(SNS)는 Anthropic API 실동작 + 스텁 fallback. Agent 3(이미지)/4(영상)는 `agents/higgsfield_client.py`를 통해 Higgsfield Platform REST API 실호출 (`higgsfield-ai/soul/standard`, `higgsfield-ai/dop/preview`) — key/secret은 `backend/.env`, 크레딧 부족 등 실패 시 스텁 강등. Soul Character 학습 API는 미공개라 `create_soul_id()`만 스텁 유지

## 불변 제약 (생성 단계의 게이트)

- **상품 원본 절대 변경 금지** — 디자인·패턴·색상·로고·소재·핏. Higgsfield reference 제어로 보존하고 생성 후 유지율(SSIM/임베딩) 검수, 미달 시 재생성 큐로 회송.
- **모델 동일성 유지** — 모든 생성에 동일 Soul ID 주입, 얼굴 동일성 점수로 검증.
- 위 두 게이트를 통과하지 못한 산출물은 배포하지 않는다.

## 작업 방식

- 작업 진행 전 애매하거나 결정이 필요한 지점은 반드시 먼저 사용자에게 질문한다 (사용자 명시 요청).
- 코드/스택을 변경하면 세 문서(PRD/TRD/개발계획서)의 정렬을 함께 유지한다. 한 문서만 바꿔 불일치를 남기지 말 것.
- 새 소스 파일 첫 줄에는 역할을 설명하는 한 줄 한국어 주석을 단다 (상위 CLAUDE.md 규칙).

## 빌드/테스트

- Backend 실행: `backend/.venv` 가상환경 사용, `backend/main.py`가 FastAPI 엔트리포인트.
- 테스트: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/` — tests.md의 Phase별 기준을 코드로 고정한 스위트.
- 검증 기준은 Phase별로 [docs/tests.md](docs/tests.md)에 정의되어 있으며, 각 Phase 완료 시 이를 충족해야 다음 Phase로 진행한다.
- Frontend/Celery/Redis 등 미도입 스택은 도입 시 이 절을 갱신할 것.
