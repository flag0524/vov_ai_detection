# status.md — 진행 현황

> 각 Phase 완료 시 이 파일을 업데이트한다. 날짜·결과·미결 이슈를 기록.

---

## 전체 진행률

| Phase | 상태 | 완료일 | 비고 |
| --- | --- | --- | --- |
| Phase 0 기반 셋업 | ✅ 완료 | 2026-06-30 | SQLite 사용, Redis 미연동 |
| Phase 1 상품 분석 & 모델 생성 | 🟡 스텁 모드 완료 | 2026-07-01 | 코드 완성, 실키/실Higgsfield 연동 대기 |
| Phase 2 이미지 생성 | 🟡 스텁 모드 완료 | 2026-07-01 | SSIM 실검증 활성화, 이미지 자체는 스텁 URL |
| Phase 3 영상 생성 | 🟡 스텁 모드 완료 | 2026-07-01 | 영상 자체는 스텁 URL |
| Phase 4 SNS 콘텐츠 | 🟡 스텁 모드 완료 | 2026-07-01 | 실키 없으면 스텁 카피 반환 |
| Phase 5 프론트엔드 & E2E | 🟡 스텁 모드 완료 | 2026-07-01 | Next.js 업로드/생성/결과 화면, CORS 연동 검증 |
| Phase 6 품질 자동화 | 🟡 스텁 모드 완료 | 2026-07-01 | 재생성 루프·처리시간 측정 구현 및 단위 검증, 실생성물 기준 재검증은 Higgsfield 연동 후 |

---

## 현재 단계: Phase 1~4 스텁 모드 완료

**날짜**: 2026-07-01
**상태**: 완료 (스텁 모드 한정). 실제 외부 API(Anthropic, Higgsfield) 연동은 키/인증 확보 후 재검증 필요.

### 배경
2026-07-01 세션 시작 시점에 확인해보니, 이 status.md가 실제 코드 상태를 반영하지 못하고 있었다. `agents/agent1~5`, `backend/app/api/{ai,pipeline,sns}.py`, `backend/app/services/{quality,queue}.py`가 이미 존재했고 Phase 1~4에 해당하는 로직(상품 분석, 프롬프트 생성, Soul ID, 이미지/영상 생성, SSIM/얼굴 유사도 검증, SNS 카피, `/pipeline/run` E2E 엔드포인트)이 구현되어 있었다. 다만:
- Agent 1/2/5(Anthropic 호출)는 `ANTHROPIC_API_KEY` 없으면 예외로 죽는 상태였음 → 스텁 fallback 추가
- Agent 3/4(Higgsfield 호출)는 이미 스텁 fallback이 있었음 (그대로 유지)
- `quality.py`의 SSIM은 scikit-image 미설치로 항상 스텁값만 반환 → 패키지 설치 후 실계산 활성화, 최신 skimage의 `data_range` 필수 인자 누락 버그 수정
- `app/api/{ai,pipeline,sns}.py`의 `sys.path.insert` 경로가 `..` 4개로 되어 있어 `agents/` 상위 폴더로 잘못 올라가는 버그 → `..` 3개로 수정 (`ModuleNotFoundError: agents`)
- Redis/RQ는 패키지만 설치돼 있고 `queue.py`의 `enqueue()`는 실제로 어디서도 호출되지 않음 (동기 처리 중) → 이번 세션에서는 보류

### 완료된 것
- Agent 1/2/5 스텁 fallback 추가 (`ANTHROPIC_API_KEY` 없어도 파이프라인 끝까지 실행 가능)
- scikit-image/opencv-python-headless 설치, `requirements.txt` 반영, SSIM 실계산 검증 (`ssim(data_range=1.0)` 버그 수정)
- `sys.path` 버그 수정 (ai.py, pipeline.py, sns.py)
- `/pipeline/run` E2E 스텁 모드 실행 검증: 상품분석→모델생성→프롬프트→이미지(스텁)→SSIM 품질검증(실계산, pass)→영상(스텁)→SNS카피(스텁) 전 구간 정상 응답 확인
- `/ai/model/create`, `/health/redis` 개별 엔드포인트 동작 확인 (Redis는 미연결 상태로 error 응답, 예상된 동작)

### 확정된 의사결정 (2026-07-01, 사용자 승인)
- Agent 1/2/5: 실키 없을 때 스텁 fallback 추가 (Agent 3/4와 동일 패턴)
- Higgsfield MCP: 이번 세션은 보류. `claude.ai` 커넥터에서 사용자가 먼저 OAuth 인증을 완료한 뒤 재요청 시 실연동 진행
- Redis: 이번 세션은 보류. 이 머신에 네이티브 redis-server/choco/scoop/WSL 배포판이 전혀 없어 설치 자체가 큰 환경 변경이 필요함. 현재 규모에서는 동기 처리로 충분하다고 판단, 스케일 필요 시점에 WSL 또는 Memurai로 도입
- SSIM: scikit-image/opencv 지금 설치해서 실검증 활성화 (완료)

### 다음 단계
- 사용자가 claude.ai Higgsfield 커넥터 인증 완료 → Agent 3/4의 `NotImplementedError` 부분을 실제 MCP 호출로 구현 → Phase 2/3 실이미지 기준 SSIM/얼굴 유사도 게이트 재검증, Phase 6 재생성 루프도 실생성물 기준 재검증
- 실 서비스 스케일 시점에 Redis(WSL 또는 Memurai) 도입 → `queue.py`를 실제 job 라우팅에 연결

### 세션 종료 시점 확정 의사결정 (2026-07-02, 사용자 승인)

Phase 1~6의 실생성물 기준 완료는 다음 두 가지 외부 인증에 막혀 이 세션 내에서 더 진행할 수 없다. 사용자에게 직접 확인해 아래로 확정했다.

| 항목 | 결정 | 사유 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` (Agent 1/2/5) | 키 미설정 상태로 스텁 모드 검증까지만 진행, 이번 세션은 종료 | 사용자가 지금 키를 제공하지 않기로 함 |
| Higgsfield MCP 인증 (Agent 3/4) | 사용자가 `claude.ai` 커넥터 설정에서 직접 OAuth 완료 후 **다음 세션**에서 재개 | OAuth는 에이전트가 대신 수행 불가능 (세션 비대화형) |

**결론**: Phase 1~6은 "스텁 모드 코드 완성 + 스텁 기준 검증 완료" 상태가 이번 세션의 최종 상태다. 실생성물(Anthropic 실호출, Higgsfield 실호출) 기준 재검증은 위 두 인증이 해결되기 전까지 보류하며, 이는 코드 미비가 아니라 외부 인증 의존성에 의한 의도된 블로킹이다.

---

## Phase 5 — 프론트엔드 & E2E (스텁 모드 완료, 2026-07-01)

### 완료된 것
- Next.js 16.2.9 (App Router, TS, Tailwind) `frontend/`에 스캐폴딩 (`npx create-next-app`, 공식 npmjs 레지스트리에서 설치 확인)
  - 참고: 스캐폴딩 시 `frontend/CLAUDE.md`, `frontend/AGENTS.md`가 자동 생성됨. 처음엔 프롬프트 인젝션으로 의심해 진행을 멈추고 조사했으나, 최신 `create-next-app`(v16 계열)이 코딩 에이전트에게 번들 문서를 참고하도록 안내하기 위해 기본 포함하는 공식 기능임을 `node_modules/next/dist/docs`로 확인 후 진행함
- 상품 업로드 → `/pipeline/run` 실행 → 화보/영상/SNS 카피 결과 확인 단일 화면 구현 (`frontend/app/page.tsx`)
- 백엔드에 CORS 미들웨어 추가 (`backend/main.py`, `localhost:3000` 허용)
- 검증: `npm run build` 통과, 프론트(3000)·백엔드(8000) 동시 기동 후 curl로 `Origin: http://localhost:3000` 헤더를 포함한 업로드→파이프라인 실행까지 CORS 정상 통과 확인, `/` 페이지 렌더링 확인
- 한계: 실제 브라우저 클릭 조작(Playwright 등)으로는 검증하지 않음 — curl + Origin 헤더로 CORS·API 계약만 검증함

## Phase 6 — 품질 자동화 (스텁 모드 완료, 2026-07-01)

### 완료된 것
- `backend/app/services/quality.py`에 `run_with_quality_gate()` 추가: 품질 게이트(SSIM ≥ 0.80) 미달 시 최대 2회까지 자동 재생성하는 루프
- `/pipeline/run`에 재생성 루프 연결, `regeneration_attempts`·`processing_time_sec`을 응답 및 `GenerationJob.result_refs`에 기록 (품질 미달로 재시도 소진 시 job status를 `failed`로 저장)
- 검증: `unittest.mock.patch`로 SSIM 점수를 인위로 낮게(0.5) 조작해 재시도 발생을 확인 — (1) 2회 실패 후 3회차 통과 시나리오에서 attempts=3, overall_pass=True (2) max_attempts=2 소진 시 attempts=2, overall_pass=False 모두 기대대로 동작
- 한계: 현재 스텁 모드에서는 생성 이미지가 항상 원본과 동일 경로라 실제로는 항상 통과함 (`overall_pass=True` 고정). 재생성 루프 "로직"은 검증했지만, 실제 서로 다른 생성물 간 SSIM 기준 재생성 트리거는 Higgsfield 실연동 후 재검증 필요
- 미구현: 브랜드 스타일 학습(JBLANC STYLE MODEL) — Phase 2/3 실생성물이 쌓인 뒤에나 의미 있는 작업이라 보류

---

## 변경 이력

| 날짜 | 내용 |
| --- | --- |
| 2026-06-30 | 문서 체계 초기 생성 (goal/plan/status/tests) |
| 2026-06-30 | Phase 0 완료: FastAPI + SQLite + 업로드 API 검증 |
| 2026-07-01 | status.md가 실제 코드(Phase 1~4 스텁 구현)를 반영 못하고 있음을 발견, 재정리 |
| 2026-07-01 | Agent 1/2/5 스텁 fallback 추가, SSIM 실검증 활성화, sys.path 버그 수정, `/pipeline/run` E2E 스텁 모드 검증 완료 |
| 2026-07-01 | Phase 5: Next.js 프론트엔드 스캐폴딩 + 업로드/생성/결과 화면 + CORS 연동 검증 완료 |
| 2026-07-01 | Phase 6: 재생성 루프(`run_with_quality_gate`) + 처리시간 측정 구현, 단위 테스트로 재시도/실패 케이스 검증 |
| 2026-07-02 | 세션 종료 시점 확정: ANTHROPIC_API_KEY 미설정 상태로 스텁 모드 검증까지만 진행, Higgsfield MCP는 사용자 OAuth 인증 후 다음 세션에서 재개하기로 결정 |
