# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

JBLANC AI Fashion Marketing Automation System. 제이블랑(JBLANC) 패션 상품 이미지를 업로드하면 AI 모델 화보 이미지·릴스 영상·SNS 카피를 자동 생성하는 마케팅 자동화 플랫폼이다.

현재 상태는 **문서 단계**다. 코드는 아직 없고 `docs/`에 PRD/TRD/개발계획서만 존재한다. 구현을 시작하기 전 반드시 이 세 문서를 읽고 정렬 상태를 유지할 것.

- [docs/PRD.md](docs/PRD.md) — 제품 요구사항(기능·플로우·KPI).
- [docs/TRD.md](docs/TRD.md) — 기술 요구사항(아키텍처·API·데이터 모델). **최신 버전 v2.0 기준.**
- [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) — Phase 0~6 로드맵·마일스톤·디렉터리 구조.

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

### 예정 스택 / 디렉터리 (TRD·개발계획서 기준, 아직 미생성)

- Frontend: Next.js (App Router, TS) — `frontend/`
- Backend: FastAPI (Python, Pydantic) — `backend/` (api: product/ai/sns 라우터)
- 비동기: Celery/RQ + Redis Job Queue — `workers/` (Higgsfield MCP 호출 비동기 처리)
- DB: PostgreSQL(메타) + pgvector/Qdrant(검수 임베딩), S3 호환 스토리지
- Agents: `agents/` (MCP Agent 1~5)

## 불변 제약 (생성 단계의 게이트)

- **상품 원본 절대 변경 금지** — 디자인·패턴·색상·로고·소재·핏. Higgsfield reference 제어로 보존하고 생성 후 유지율(SSIM/임베딩) 검수, 미달 시 재생성 큐로 회송.
- **모델 동일성 유지** — 모든 생성에 동일 Soul ID 주입, 얼굴 동일성 점수로 검증.
- 위 두 게이트를 통과하지 못한 산출물은 배포하지 않는다.

## 작업 방식

- 작업 진행 전 애매하거나 결정이 필요한 지점은 반드시 먼저 사용자에게 질문한다 (사용자 명시 요청).
- 코드/스택을 변경하면 세 문서(PRD/TRD/개발계획서)의 정렬을 함께 유지한다. 한 문서만 바꿔 불일치를 남기지 말 것.
- 새 소스 파일 첫 줄에는 역할을 설명하는 한 줄 한국어 주석을 단다 (상위 CLAUDE.md 규칙).

## 빌드/테스트

아직 코드·빌드 시스템이 없다. 스캐폴딩 후 이 절에 build/lint/test 및 단일 테스트 실행 명령을 채울 것.
