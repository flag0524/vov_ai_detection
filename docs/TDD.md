# TDD — Technical Design Document

- 문서 버전: v1.0
- 작성일: 2026-07-05
- 위치: PRD(무엇을) → TRD(요구 스펙) → **TDD(실제로 어떻게 구현되어 있는가)**. 이 문서는 현재 코드베이스의 실측 설계를 기록하며, TRD와 달라진 부분은 근거(ADR 번호)를 명시한다.

---

## 1. 시스템 구성 (실구현 기준)

```
[Next.js 16 Frontend]  frontend/app/page.tsx (업로드→생성→결과 단일 화면)
        │  fetch, CORS(localhost:3000)
        ▼
[FastAPI Backend]  backend/main.py
  ├─ /health, /health/redis          backend/app/api/health.py
  ├─ /product/upload, /product/{id}  backend/app/api/product.py
  ├─ /ai/model/create, /ai/image/generate, /ai/video/generate  backend/app/api/ai.py
  ├─ /sns/content/create             backend/app/api/sns.py
  ├─ /jobs/{job_id}                  backend/app/api/jobs.py
  └─ /pipeline/run  (E2E 오케스트레이션)  backend/app/api/pipeline.py
        │  함수 직접 호출 (동기, ADR-007)
        ▼
[Agents]  agents/
  ├─ agent1_product_analyzer.py   Anthropic Vision → 상품 메타 JSON
  ├─ agent2_prompt_engineer.py    Anthropic → 화보 프롬프트 JSON
  ├─ agent3_fashion_model.py      Higgsfield soul/standard → 이미지
  ├─ agent4_video_creator.py      Higgsfield dop/preview → 영상 (image-to-video)
  ├─ agent5_marketing.py          Anthropic → 캡션/해시태그/광고카피
  ├─ higgsfield_client.py         Platform REST 공용 클라이언트 (submit→poll)
  └─ orchestrator.py              백엔드 없이 단독 실행용 파이프라인 러너
        │
        ▼
[External]  Anthropic API (claude-sonnet-4-6) · Higgsfield Platform API
[Storage]   SQLite backend/jblanc.db · 로컬 storage/uploads, storage/results
```

## 2. 디렉터리 구조

```
vov_ai_detection/
├── docs/            PRD, TRD, TDD, ADR, DEVELOPMENT_PLAN, goal, plan, status, tests
├── frontend/        Next.js 16 (App Router, TS, Tailwind)
├── backend/
│   ├── main.py      FastAPI 엔트리포인트 (CORS, 라우터 등록, create_all)
│   ├── .env         API 자격증명 (gitignore 대상)
│   ├── app/api/     라우터 6종
│   ├── app/models/  base.py(엔진/세션), entities.py(ORM 4테이블)
│   ├── app/services/ quality.py(품질 게이트), queue.py(RQ 헬퍼, 미연결)
│   └── tests/       pytest 스위트 (conftest + test_api + test_quality)
├── agents/          Agent 1~5 + higgsfield_client + orchestrator
├── storage/         uploads/(원본), results/(생성물 저장 예정)
└── workers/         비동기 워커 (Redis 도입 시 사용, 현재 빈 디렉터리)
```

## 3. 데이터 모델 (SQLAlchemy ORM, 실스키마)

TRD §3의 설계와 달리 `face_embedding` 컬럼은 없다 (ADR-003, Soul ID로 대체).

### ai_models
| 컬럼 | 타입 | 비고 |
|---|---|---|
| model_id | String PK | uuid4 |
| soul_reference_id | String | Higgsfield Soul ID. 미학습 시 `STUB_SOUL_*` (ADR-008) |
| body_style / hair_style / age / mood / fashion_style | String | 모델 속성 |
| created_at | DateTime(tz) | |

### products
| 컬럼 | 타입 | 비고 |
|---|---|---|
| product_id | String PK | uuid4 |
| name, category, color, material, silhouette, season, style, target_customer | String | Agent 1 분석 결과 반영 가능 |
| image_ref | String | 로컬 저장 경로 (S3 전환 시 URL) |

### generation_jobs
| 컬럼 | 타입 | 비고 |
|---|---|---|
| job_id | String PK | uuid4 |
| type | Enum(soul, image, video) | |
| product_id / model_id | FK | nullable |
| status | Enum(queued, running, done, failed) | 동기 처리라 현재 done/failed로 직행 |
| mcp_call_ref | String | Higgsfield request_id 저장용 |
| params | JSON | prompt, background 등 재현용 파라미터 |
| result_refs | JSON | image_url/video_url + quality + regeneration_attempts + processing_time_sec |

### contents
| 컬럼 | 타입 | 비고 |
|---|---|---|
| content_id | String PK | |
| source_ref | String | product_id |
| caption / ad_copy | String | Agent 5 산출 |
| hashtags | JSON | 배열 |
| channel | String | instagram |
| status | String | draft → (검수 후) published 예정 |

## 4. API 설계 (실구현)

TRD §7의 `/api/v1/*` 프리픽스 대신 리소스 직접 프리픽스를 사용한다.

| Method | Endpoint | 요청 | 응답 핵심 필드 |
|---|---|---|---|
| GET | /health | — | `{status: ok}` |
| GET | /health/redis | — | Redis 연결 상태 (미연결 시 error, 정상 동작) |
| POST | /product/upload | multipart file | product_id, image_ref. 손상 이미지는 400 |
| GET | /product/{id} | — | 상품 메타 |
| POST | /ai/model/create | 모델 속성 JSON | model_id, soul_reference_id, stub |
| POST | /ai/image/generate | product_id, model_id, background | job_id, image_url, prompt, stub |
| POST | /ai/video/generate | image_url, duration_sec(5~15), camera_motion | job_id, video_url, stub |
| POST | /sns/content/create | product_id | content_id, caption, hashtags, ad_copy |
| GET | /jobs/{job_id} | — | job 상태·result_refs |
| POST | /pipeline/run | product_id, model_id?, background? | 아래 §5 참조 |

## 5. E2E 파이프라인 시퀀스 (`POST /pipeline/run`)

```
1. Product 조회 (없으면 404)
2. Agent 1  analyze_product_image(image_ref)        → product_meta
3. AIModel 재사용 또는 신규: Agent 3 create_soul_id() → soul_reference_id
4. Agent 2  generate_photoshoot_prompt(meta, attrs)  → prompt
5. run_with_quality_gate(                             ← 품질 게이트 루프 (ADR-009)
     generate_fn = Agent 3 generate_image(prompt, soul_id, ...),
     SSIM ≥ 0.80 통과까지 최대 2회 재생성)
6. Agent 4  generate_video(image_url, 9:16, 5~15s)   → video_url
7. Agent 5  generate_sns_content(product_meta)       → caption/hashtags/ad_copy
8. GenerationJob(image, video) + Content 저장
9. 응답: 산출물 3종 + quality + regeneration_attempts
        + processing_time_sec + stubs{image, video}
```

품질 게이트 소진 시 job status=`failed`로 저장하고 배포 대상에서 제외한다 (불변 제약).

## 6. 에이전트 설계

### 공통 패턴 — 스텁 강등 (ADR-005)
모든 에이전트는 동일한 2단 방어를 가진다.
1. 자격증명 미설정 → 즉시 스텁 반환 (`stub: true`)
2. API 호출 실패 (크레딧 부족·4xx/5xx·타임아웃) → 예외를 삼키고 스텁 반환 (`stub: true, reason: <원인>`)

호출부는 `stub` 플래그만 보고 실생성물 여부를 판단한다. 예외 전파로 파이프라인이 죽는 경로는 없다.

### Agent 1 — 상품 분석
- 입력: 이미지 경로 → base64 인코딩, 확장자별 media_type 매핑
- 모델: `claude-sonnet-4-6`, max_tokens 512, JSON 강제 시스템 프롬프트
- 출력: category/color/material/silhouette/season/style/target_customer
- JSON 파싱 실패 시 `{raw, parse_error: true}` 반환 (죽지 않음)

### Agent 2 — 프롬프트 엔지니어
- 입력: product_meta + model_attrs + background
- 시스템 프롬프트에 원본 보존 지시·Vogue 스타일·200토큰 제한 내장
- 출력: `{prompt, negative_prompt}`

### Agent 3 — 이미지 생성
- `create_soul_id()`: 학습 API 미공개로 스텁 유지 (ADR-008)
- `generate_image()`: `higgsfield_client.generate("higgsfield-ai/soul/standard", {prompt, ...})` → 완료 폴링 → image_url

### Agent 4 — 영상 생성
- duration 5~15초 검증 (범위 밖 ValueError), aspect_ratio 9:16 고정
- `higgsfield_client.generate("higgsfield-ai/dop/preview", {image_url, ...})` → video_url

### Agent 5 — SNS 카피
- 브랜드 톤(럭셔리·감각·여성) 시스템 프롬프트, `#제이블랑` 해시태그 보장
- 출력: `{caption, hashtags[≥8], ad_copy}`

### higgsfield_client — 공용 REST 클라이언트 (ADR-004)
- `submit(model_id, payload)` → POST `platform.higgsfield.ai/{model_id}` → request_id
- `wait(request_id)` → GET `/requests/{id}/status` 3초 간격 폴링, completed/failed/timeout(300s)
- 인증: `Authorization: Key {HIGGSFIELD_API_KEY}:{HIGGSFIELD_API_SECRET}`
- 실패는 전부 `HiggsfieldError`로 정규화 → 에이전트가 스텁 강등에 사용

## 7. 품질 게이트 설계 (`app/services/quality.py`)

| 게이트 | 지표 | 임계값 | 미달 시 |
|---|---|---|---|
| 상품 원본 유지 | SSIM (scikit-image, grayscale, `data_range=1.0`) | ≥ 0.80 | 재생성 (최대 2회) → 소진 시 failed |
| 모델 얼굴 동일성 | 임베딩 코사인 유사도 | ≥ 0.85 | 재생성. 임베딩 미입력 시 스킵(조건부 게이트) |

- `validate_generation()` → `{ssim_score, product_pass, face_similarity, face_pass, overall_pass, action}`
- `run_with_quality_gate(generate_fn, ...)` → `(생성 결과, quality, attempts)` — 게이트 통과 또는 시도 소진까지 루프
- TRD의 naturalness_score(동작·표정 자연스러움)는 **미구현**. 실생성물이 나오기 시작하면 도입한다 (개발계획서 v2.0 후속 트랙).

## 8. 환경변수 (`backend/.env`)

| 변수 | 용도 |
|---|---|
| ANTHROPIC_API_KEY | Agent 1/2/5 |
| HIGGSFIELD_API_KEY / HIGGSFIELD_API_SECRET | Agent 3/4 (쌍으로 필요) |
| DATABASE_URL | 기본 `sqlite:///./jblanc.db`, 운영 시 PostgreSQL DSN |
| STORAGE_LOCAL_DIR | 기본 `../storage` |
| REDIS_URL | queue.py용 (현재 미사용, ADR-007) |

## 9. 테스트 설계 (`backend/tests/`, pytest 17건)

- **격리**: conftest가 인메모리 SQLite(StaticPool) + 임시 스토리지로 `get_db`/`STORAGE_DIR`를 오버라이드 — 개발 DB·storage 오염 없음
- **test_api.py**: 헬스체크, ORM 4테이블 존재, 업로드→조회, model/create(Soul 스텁), pipeline/run E2E(산출물 3종+게이트+스텁 플래그), 404, SNS 해시태그, 영상 duration 경계
- **test_quality.py**: SSIM 동일=1.0/반전<0.80, requeue 액션, 얼굴 유사도 경계, 임베딩 없을 때 스킵, 재생성 루프(재시도 후 통과/소진 실패/1회 통과)
- 실행: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/`

## 10. 알려진 설계 부채 / 후속 과제

1. **동기 파이프라인** — 실생성(폴링 수 분) 기준으로는 HTTP 타임아웃 위험. Redis 도입 시 job 큐로 이관 (ADR-007)
2. **naturalness QA 미구현** — PRD FR-7 / TRD §4 validate_naturalness()는 실생성물 확보 후 착수
3. **Soul 학습 API 미공개** — FR-2 얼굴 고정의 완전 충족 불가, `create_soul_id()` 스텁 (ADR-008)
4. **생성물 로컬 보관 미구현** — 현재 Higgsfield가 반환한 URL을 그대로 저장. `storage/results/` 다운로드 보관 및 S3 전환 필요
5. **인스타그램 발행 미구현** — Content는 draft까지만 (PRD 범위상 등록 준비까지)
