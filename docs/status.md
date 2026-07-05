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

## 목표 완료 확정 (2026-07-03, 사용자 승인)

**Phase 0~6 전체를 스텁 모드 기준으로 목표 완료 처리한다.** 검증 근거는 pytest 17건 전부 통과 + 실브라우저 클릭 E2E 통과. 실생성물 기준 재검증은 별도 요청으로 진행하며, 선결 조건은 다음 두 가지다.
1. Higgsfield 크레딧 충전 (cloud.higgsfield.ai) — 충전 즉시 코드 변경 없이 Agent 3/4 실생성 동작 (인증 검증 완료 상태)
2. `ANTHROPIC_API_KEY` 제공 → `backend/.env` 추가 — Agent 1/2/5 실동작

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

## Higgsfield REST 실연동 (2026-07-03)

### 완료된 것
- 사용자로부터 Higgsfield API key + secret 수령 → `backend/.env` 저장 (gitignore 대상)
- **인증 검증 성공**: `Authorization: Key {key}:{secret}` 형식으로 `platform.higgsfield.ai` 호출 시 401→403 전환 확인 (자격증명 유효)
- `agents/higgsfield_client.py` 신규: submit→poll 패턴 공용 REST 클라이언트
- Agent 3 `generate_image()`: `higgsfield-ai/soul/standard` 실호출로 전환
- Agent 4 `generate_video()`: `higgsfield-ai/dop/preview` (image-to-video) 실호출로 전환, camera_motion→프롬프트 매핑
- API 실패(크레딧 부족 등) 시 파이프라인을 죽이지 않고 스텁으로 강등하며 `reason`에 사유 기록 — 실검증 완료 (`403 not_enough_credits` → stub 강등 확인)
- pytest 자동 테스트 스위트 신설 (`backend/tests/`, 16건 전부 통과): tests.md의 Phase 0~6 스텁 검증 기준을 코드로 고정

### 현재 블로커
1. **Higgsfield 크레딧 부족** (`not_enough_credits`) — 계정에 크레딧 충전 필요. 충전 즉시 코드 변경 없이 실생성 동작
2. **Soul Character 학습 API 미공개** — Platform API 공개 문서에 text2image(`soul/standard`)만 존재. `create_soul_id()`는 스텁 유지, 학습 API 공개 시 해당 함수만 교체
3. **Anthropic 크레딧 부족** — 2026-07-03 사용자가 ANTHROPIC_API_KEY 제공 → `.env` 저장, 키 인증은 유효하나 계정 잔액 0 (`credit balance is too low`). 콘솔(Plans & Billing)에서 충전 즉시 Agent 1/2/5 실동작. 이 과정에서 "키는 있으나 API 실패" 시 파이프라인이 500으로 죽는 갭 발견 → Agent 1/2/5도 Agent 3/4처럼 API 실패 시 스텁 강등 + `reason` 기록하도록 수정 (실검증 완료)

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
- ~~한계: 실제 브라우저 클릭 조작(Playwright 등)으로는 검증하지 않음~~ → **2026-07-03 해소**: Chrome DevTools로 실브라우저 클릭 E2E 수행 (파일 선택→생성 시작→화보/영상/SNS 카피 결과 렌더링 확인). 이 과정에서 손상 이미지 업로드 시 `/pipeline/run`이 언핸들드 500으로 죽고 브라우저에는 CORS 오류로 위장 표시되는 버그 발견 → 업로드 시점 PIL 검증으로 400 거부하도록 수정, 회귀 테스트 추가 (총 17건 통과)

## Phase 6 — 품질 자동화 (스텁 모드 완료, 2026-07-01)

### 완료된 것
- `backend/app/services/quality.py`에 `run_with_quality_gate()` 추가: 품질 게이트(SSIM ≥ 0.80) 미달 시 최대 2회까지 자동 재생성하는 루프
- `/pipeline/run`에 재생성 루프 연결, `regeneration_attempts`·`processing_time_sec`을 응답 및 `GenerationJob.result_refs`에 기록 (품질 미달로 재시도 소진 시 job status를 `failed`로 저장)
- 검증: `unittest.mock.patch`로 SSIM 점수를 인위로 낮게(0.5) 조작해 재시도 발생을 확인 — (1) 2회 실패 후 3회차 통과 시나리오에서 attempts=3, overall_pass=True (2) max_attempts=2 소진 시 attempts=2, overall_pass=False 모두 기대대로 동작
- 한계: 현재 스텁 모드에서는 생성 이미지가 항상 원본과 동일 경로라 실제로는 항상 통과함 (`overall_pass=True` 고정). 재생성 루프 "로직"은 검증했지만, 실제 서로 다른 생성물 간 SSIM 기준 재생성 트리거는 Higgsfield 실연동 후 재검증 필요
- 미구현: 브랜드 스타일 학습(JBLANC STYLE MODEL) — Phase 2/3 실생성물이 쌓인 뒤에나 의미 있는 작업이라 보류

---

## 실생성 검증 1차 (2026-07-05) — Higgsfield 크레딧 충전 확인

### 실측 결과
| 항목 | 결과 |
| --- | --- |
| 이미지 실생성 (Agent 3, `soul/standard`) | ✅ 성공 — CloudFront URL, 실사 화보급 품질, naturalness 지시어 반영 확인 (18.6초) |
| 영상 실생성 (Agent 4) | ✅ 성공 — 단 `dop/preview` 슬러그가 422로 거부되어 `dop/standard`로 수정 후 성공 |
| 영상 규격 | 길이 5.4초 ✅ (기준 5~15초) / 해상도 816x1104 ❌ (9:16 아님 — 입력 이미지 비율 3:4를 따라감. 이미지 생성 단계에서 9:16 출력 필요, A-3 후속) |
| SSIM 실측 | **0.566 — 게이트(0.80) 구조적 탈락.** 상품 단독 사진 vs 모델 착용 화보 전체 비교는 구도가 달라 0.80 도달 불가 |
| Agent 1/2/5 (Anthropic) | 여전히 스텁 (크레딧 0 유지) |

### 발견된 문제와 조치
- `test_product.jpg`가 실상품이 아닌 남색 도형 플레이스홀더임을 확인 — 의미 있는 상품 보존 검증에는 실제 JBLANC 상품 사진 필요
- 실키 설정 후 pytest가 유료 API를 실호출하는 문제 발견 → conftest에 강제 스텁 모드(autouse) 추가, 실생성 검증은 의도된 수동 실행으로 분리
- B-1 완료: PRD FR-7 naturalness 지시어·Negative Prompt를 Agent 2(이미지)·Agent 4(영상 모션)에 내장, 테스트로 고정
- B-3 완료: 인스타 포맷 산출 모듈(`export.py` — Feed 1080x1350, Reel/Story 1080x1920 센터크롭+리사이즈) 구현, 테스트 6건

### 의사결정 확정 (2026-07-05, 사용자 승인)
1. **SSIM 게이트 완화 (ADR-011)**: 정보성 점수 + manual_review로 전환. 자동 재생성/failed 폐기, 파이프라인은 1회 생성 후 실생성물 다운로드→실SSIM 기록. 반영 완료 (23건 테스트 통과)
2. **실제 상품 이미지**: 사용자가 준비 예정 — 확보 시 상품 보존 정밀 재검증
3. **Anthropic 크레딧**: 당분간 스텁 유지 (상품 분석·SNS 카피는 실상품 미반영 한계 유지)
4. **향후 실생성 진행은 Higgsfield API 키 방식으로 확정** — claude.ai MCP 커넥터가 아닌 Platform REST API(key/secret) 경로가 파이프라인의 기본 경로 (ADR-004 유지)
5. **Anthropic API 미사용 확정 (2026-07-05)** — Agent 1/2/5는 Anthropic을 사용하지 않는다 (ADR-010 폐기 방향). 대체 방안(규칙 기반 정식화 vs 타 LLM)은 사용자 확인 대기

### 실브라우저 E2E 검증 (2026-07-05)
- Chrome DevTools로 실브라우저 클릭 조작 검증 완료: 파일 업로드 → "생성 시작" 클릭 → 화보/영상/SNS카피 3종 렌더링 확인 (백엔드는 키 비활성 스텁 모드로 기동해 크레딧 소모 없음)
- tests.md Phase 5의 마지막 갭("실브라우저 클릭 미검증") 해소
- 프론트 배너 문구를 실상에 맞게 수정 ("MCP 미연동" → "외부 생성 API 미호출")

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
| 2026-07-03 | pytest 스위트 16건 구축·통과. 사용자 제공 Higgsfield key+secret으로 REST 실연동 코드 완성 (Agent 3/4), 인증 검증 성공, 크레딧 부족(`not_enough_credits`)으로 실생성만 대기 |
| 2026-07-03 | 실브라우저 클릭 E2E 검증 완료 (Phase 5 한계 해소). 손상 이미지 업로드 → 500 크래시 버그 발견·수정 (업로드 시점 400 거부, 회귀 테스트 포함 17건 통과). 4바이트 더미 업로드 파일 정리 |
| 2026-07-03 | **목표 완료 확정 (사용자 승인)**: Phase 0~6 스텁 모드 기준 완료 처리. 실생성물 재검증은 크레딧 충전/ANTHROPIC_API_KEY 확보 후 별도 요청으로 진행 |
| 2026-07-03 | 사용자 제공 ANTHROPIC_API_KEY `.env` 저장 — 키 유효하나 Anthropic 계정 잔액 0. Agent 1/2/5에 API 실패 시 스텁 강등 추가 (파이프라인 500 방지), 17건 테스트 통과 |
