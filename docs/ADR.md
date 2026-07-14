# ADR — Architecture Decision Records

- 문서 버전: v1.0
- 작성일: 2026-07-05
- 목적: 프로젝트 진행 중 확정된 아키텍처 의사결정을 결정 단위로 기록한다. 각 결정의 배경과 근거를 남겨, 이후 세션(사람 또는 에이전트)이 같은 논의를 반복하지 않도록 한다.

상태 표기: ✅ 채택 | 🔄 부분 채택(조건부) | ⏸ 보류 | ❌ 폐기

---

## ADR-001. 이미지·영상 생성 인프라 = Higgsfield (자체 추론 없음) ✅

- **일자**: 2026-06-30 (TRD v2.0에서 확정)
- **컨텍스트**: 자체 Diffusion / IP Adapter / ControlNet 추론 인프라를 구축할지, 외부 생성 API를 쓸지 결정 필요. 자체 인프라는 GPU 비용·운영 부담이 크고, 얼굴 일관성 유지를 위한 파인튜닝 파이프라인도 직접 만들어야 한다.
- **결정**: 이미지·영상 생성은 전부 Higgsfield로 처리한다. 자체 추론 인프라는 두지 않는다.
- **결과**: GPU 인프라 비용 0. 대신 Higgsfield 크레딧 비용과 외부 API 의존(가용성·기능 제약)이 생김. 상품 원본 보존은 Higgsfield reference 제어 + 생성 후 SSIM 검수로 보완.

## ADR-002. 호출 경로 = 에이전트가 생성 API 직접 호출, 백엔드는 오케스트레이션만 ✅

- **일자**: 2026-06-30
- **컨텍스트**: FastAPI 백엔드가 Higgsfield를 직접 부를지, 에이전트 레이어(`agents/`)가 부를지.
- **결정**: 백엔드는 작업(job) 위임·상태 관리·품질 게이트만 담당하고, 생성 호출은 Agent 3/4가 직접 수행한다.
- **결과**: 백엔드와 생성 로직이 분리되어 에이전트를 독립적으로 교체·테스트 가능. `backend/app/api/*`는 `agents/*` 함수를 import해 호출하는 구조.

## ADR-003. 모델 얼굴 일관성 = Soul ID (face_embedding 개념 폐기) ✅

- **일자**: 2026-06-30 (TRD v2.0)
- **컨텍스트**: 구 설계는 얼굴 임베딩(`face_embedding` VECTOR)을 저장해 매 생성마다 identity reference로 주입하는 방식이었다. Higgsfield는 Soul Character를 1회 학습하면 `soul_reference_id`로 동일 인물을 재생성하는 기능을 제공한다.
- **결정**: 모델당 1회 Soul Character를 학습해 `soul_reference_id`를 저장하고 모든 생성에 주입한다. 구 `face_embedding` 저장 개념은 폐기하되, 생성물 동일성 점수 계산용 검수 임베딩은 별도 보관한다.
- **결과**: `ai_models.soul_reference_id` 컬럼으로 구현. 단, Soul Character 학습 API가 미공개라 `create_soul_id()`는 스텁 유지 중 (ADR-008 참조).

## ADR-004. Higgsfield 연동 방식 = MCP가 아닌 Platform REST API 🔄

- **일자**: 2026-07-04
- **컨텍스트**: 당초 TRD는 "Higgsfield MCP" 연동을 전제했다. 그러나 백엔드 파이프라인(Python)이 claude.ai 커넥터 MCP를 직접 호출할 수 없고, 사용자가 Platform API key/secret을 발급받으면서 REST 경로가 열렸다.
- **결정**: Agent 3/4는 `agents/higgsfield_client.py`(submit → poll 패턴)를 통해 Platform REST API(`platform.higgsfield.ai`)를 호출한다. 이미지는 `higgsfield-ai/soul/standard`, 영상은 `higgsfield-ai/dop/preview`. 인증은 `Authorization: Key {key}:{secret}` 헤더, 자격증명은 `backend/.env`.
- **결과**: 백엔드 파이프라인이 사람 개입 없이 생성 호출 가능. claude.ai Higgsfield MCP는 대화형 세션의 보조 수단으로 병행 가능. "MCP 직접 호출"이라는 문서 표현은 "Higgsfield API 직접 호출"로 일반화됨.

## ADR-005. 외부 API 실패 시 스텁 강등 (Graceful Degradation) ✅

- **일자**: 2026-07-01 (Agent 3/4), 2026-07-03 (Agent 1/2/5로 확대)
- **컨텍스트**: 파이프라인은 외부 API 2종(Anthropic, Higgsfield)에 의존한다. 키 미설정·크레딧 부족·일시 장애 시 파이프라인 전체가 500으로 죽으면 E2E 개발·검증이 불가능하다.
- **결정**: 모든 에이전트는 (1) 자격증명 미설정 또는 (2) API 호출 실패 시 예외를 전파하지 않고 스텁 결과로 강등한다. 강등 결과에는 반드시 `stub: true`와 실패 사유(`reason`)를 포함해 실생성물로 오인되지 않게 한다.
- **결과**: 크레딧 0 상태에서도 E2E 파이프라인이 완주 가능. 응답의 `stubs` 필드로 어느 단계가 스텁인지 추적 가능. 크레딧 충전 시 코드 변경 없이 실생성으로 전환된다.

## ADR-006. DB = SQLite(개발) → PostgreSQL(운영), Storage = 로컬 → S3 ✅

- **일자**: 2026-06-30
- **컨텍스트**: 개발 머신에 Docker가 없어 PostgreSQL 컨테이너 운용이 어렵고, 초기엔 단일 사용자 개발이라 동시성 요구가 낮다.
- **결정**: 개발은 SQLite(`backend/jblanc.db`) + 로컬 파일시스템(`storage/`), 운영 전환 시 PostgreSQL + S3 호환 스토리지로 이행한다. ORM(SQLAlchemy)을 통해 DB 교체 비용을 최소화한다.
- **결과**: `DATABASE_URL` 환경변수 하나로 전환 가능. pgvector(검수 임베딩)는 PostgreSQL 전환 시점에 도입.

## ADR-007. Redis/Celery 비동기 큐 보류, 현재는 동기 처리 ⏸

- **일자**: 2026-07-01
- **컨텍스트**: TRD는 Celery/RQ + Redis job queue를 전제하나, 개발 머신에 redis-server·WSL·choco 등 설치 인프라가 전혀 없어 도입 자체가 큰 환경 변경이다. 현재 트래픽(단일 사용자, 상품 단건 처리)에서는 동기 처리로 충분하다.
- **결정**: Redis 도입을 보류하고 `/pipeline/run`은 동기 실행한다. `backend/app/services/queue.py`(RQ enqueue 헬퍼)는 작성해 두되 연결하지 않는다. 스케일 필요 시점에 WSL 또는 Memurai로 도입한다.
- **결과**: 파이프라인 1건이 HTTP 요청 시간 안에 완료되어야 하는 제약이 생김 (현재 스텁 기준 수 초, 실생성 기준 폴링 포함 수 분 예상 — 실연동 후 타임아웃 재평가 필요).

## ADR-008. Soul Character 학습은 스텁 유지 (학습 API 미공개) ⏸

- **일자**: 2026-07-04
- **컨텍스트**: Higgsfield Platform API 공개 문서에는 text2image(`soul/standard`) 계열만 있고, Soul Character를 새로 학습시키는 API는 미공개다.
- **결정**: `create_soul_id()`는 스텁 ID(`STUB_SOUL_*`)를 반환하도록 유지하고, 학습 API가 공개되면 이 함수만 교체한다. 이미지 생성은 Soul ID 없이도 `soul/standard` 모델의 기본 인물 생성으로 진행 가능.
- **결과**: "동일 모델 얼굴 고정" 요구(PRD FR-2)는 학습 API 공개 전까지 완전 충족 불가. 얼굴 일관성 게이트는 검수 임베딩 입력 시에만 계산되는 조건부 게이트로 동작.

## ADR-009. 품질 게이트 = SSIM 실계산 + 자동 재생성 루프 (최대 2회) ✅

- **일자**: 2026-07-01
- **컨텍스트**: 불변 제약 "상품 원본 절대 변경 금지"를 코드 레벨에서 강제해야 한다. 기준 미달 산출물이 그대로 배포되는 것을 막는 장치 필요.
- **결정**: scikit-image 기반 SSIM(임계 0.80)과 얼굴 임베딩 코사인 유사도(임계 0.85)를 `quality.py`에서 계산하고, `run_with_quality_gate()`가 미달 시 최대 2회 자동 재생성한다. 소진 시 job을 `failed`로 기록하고 배포하지 않는다.
- **결과**: pytest로 재시도·소진·통과 시나리오 검증 완료. 스텁 모드에서는 생성물=원본이라 항상 통과하므로, 실생성물 기준 임계값 튜닝은 Higgsfield 크레딧 충전 후 과제로 남음.

## ADR-010. Agent 1/2/5 = Anthropic API (claude-sonnet-4-6) ❌ (ADR-012로 대체)

- **일자**: 2026-07-01 → **2026-07-05 폐기**
- **컨텍스트**: 상품 이미지 분석(Vision), 생성 프롬프트 작성, SNS 카피 작성을 Anthropic Messages API로 처리했다.
- **폐기 사유**: 사용자가 Anthropic API 미사용을 확정 (비용·의존성). ADR-012 참조.

## ADR-011. SSIM은 정보성 점수 + manual_review (하드 게이트 폐기, ADR-009 일부 대체) ✅

- **일자**: 2026-07-05 (사용자 승인)
- **컨텍스트**: Higgsfield 실생성 1차 검증에서 실측 SSIM이 0.566으로 나왔다. 상품 단독 사진과 모델 착용 화보 전체를 비교하는 구조라 0.80 임계값은 도달 불가능하고, 하드 게이트를 유지하면 매 실행 재생성 2회 크레딧만 소모한 뒤 전부 failed 처리된다.
- **결정**: SSIM 미달 시 자동 재생성/failed 대신 `action: manual_review`로 표시만 하고 사람이 검수한다. 파이프라인은 1회 생성 후 실생성물을 `storage/results/`에 내려받아 실제 SSIM을 기록한다. `run_with_quality_gate()` 재생성 루프는 추후 상품 영역 크롭 비교·임베딩 유사도 등 정밀 게이트 도입 시 재사용하기 위해 유지한다.
- **결과**: ADR-009의 "미달 시 최대 2회 자동 재생성"은 정밀 게이트 도입 전까지 비활성. `generation_jobs.result_refs.qa_status`(approved | manual_review)로 검수 대상 식별. 크레딧 소모 예측 가능(생성 1회/실행).

## ADR-012. 상품 정보 직접 입력 + 규칙 기반 템플릿 (Anthropic 폐기, ADR-010 대체) ✅

- **일자**: 2026-07-05 (사용자 승인)
- **컨텍스트**: 사용자가 Anthropic API 미사용을 확정했다. Agent 1(상품 Vision 분석)/2(프롬프트 작성)/5(SNS 카피)의 대체 방식이 필요했다.
- **결정**:
  - **Agent 1 폐기** — 상품 정보(상품명·카테고리·색상·소재·스타일·타깃)는 업로드 시 담당자가 직접 입력한다 (`POST /product/upload` Form 필드 + 프론트 입력 폼). Vision 자동 분석 없음.
  - **Agent 2 = 규칙 기반 템플릿** — 입력된 상품 정보 + 모델 속성 + naturalness 지시어(FR-7)를 결정적으로 조립. 외부 API 없음.
  - **Agent 5 = 규칙 기반 템플릿** — 카테고리별 해시태그 매핑 + 캡션/광고카피 템플릿. 외부 API 없음.
  - `anthropic` 패키지 제거.
- **결과**: LLM 비용 0, 파이프라인 완전 결정적(스텁/실물 구분은 Higgsfield 생성 단계에만 존재). 트레이드오프: 프롬프트·카피의 다양성/품질이 템플릿 수준으로 제한 — 필요 시 템플릿 고도화 또는 타 LLM 재도입은 별도 ADR로 결정.

## ADR-013. 영상 생성을 이미지 승인 이후로 이연 (검수 게이트 중심 재설계) ✅

- **일자**: 2026-07-06 (사용자 승인, /grill-me 인터뷰로 확정)
- **컨텍스트**: 현재 파이프라인은 이미지+영상을 한 번에 생성한다. 실측상 실생성 이미지는 대부분 manual_review 대상인데, 검수에서 이미지가 재생성되면 기존 영상(옛 이미지 기반)이 무용지물이 되어 영상 크레딧(이미지보다 고가)이 낭비된다.
- **결정** (함께 확정된 검수 UI 설계 포함):
  1. 파이프라인(`/pipeline/run`)은 **이미지+SNS 카피까지만** 생성. 영상은 검수 승인 시 트리거
  2. 검수 UI는 **목록(/review) + 상세(/review/{job_id}) 풀 구현** — 원본/생성물 비교 뷰, QA 점수, 승인/재생성/폐기
  3. 재생성은 **프롬프트 수정 가능한 텍스트박스 + 크레딧 소모 확인** 후 실행
  4. 승인/폐기는 **job(qa_status)+Content(status) 묶음 상태 전이** — approved만 배포준비 풀 진입 (미승인 배포 금지 불변제약의 데이터 강제)
  5. 이미지 서빙은 **FastAPI StaticFiles로 storage/ 마운트** (CDN 만료 무관, S3 전환 시 경로만 교체)
  6. E2E 기준은 **2구간 분리 측정** — 자동 구간(업로드→이미지+카피) ≤10분 + 승인 후 구간(승인→영상) ≤10분, 사람 대기시간 측정 제외
  7. 승인 건에 **인스타 포맷 다운로드(Feed/Reel/Story) + 캡션 복사** 포함 (export.py API 연결)
- **개발 방식**: PR #1은 즉시 머지, 검수 UI는 `feature/review-ui` 새 브랜치. 개발·테스트는 스텁 모드(크레딧 0), 완성 후 실생성 1회로 승인→영상 흐름 최종 확인
- **결과**: 재생성 루프에서 영상 크레딧 낭비 제거, "생성→검수→배포준비" 운영 루프가 한 화면에서 완결. PRD "무인 파이프라인" 문구는 "자동 구간 + 승인 게이트" 구조로 재해석 (tests.md 기준 개정 필요)

## ADR-014. 전속 가상 모델 운영 계획 — Elements(참조) 방식 얼굴 고정 + 파일럿 GO/NO-GO ✅

- **일자**: 2026-07-06 (사용자 승인, /grill-me 인터뷰로 확정)
- **컨텍스트**: "VOV 퀄리티가 나온다면 제이블랑 인스타 홍보를 AI로 제작"이라는 비즈니스 목표. 제약: 모델 얼굴 동일, 영상 움직임·배경 자연스러움, VOV 인스타 벤치마크. 프로브로 확인된 신규 사실: Platform API에 `soul/{standard|reference|character}` 3개 모드가 존재하며 `custom_reference_id`(UUID)·`style_id`(UUID)·`seed`(int) 파라미터를 받는다 — MCP 구독 없이 참조 기반 얼굴 고정이 가능할 수 있음 (MCP 계정은 free/0 유지).
- **결정**:
  1. **얼굴 동일성 = Elements(참조 이미지) 방식** — Soul 학습(MCP 구독 필요) 대신 `soul/character` + `custom_reference_id` 경로. 등록 방법 확인이 기술검증 1순위
  2. **전속 모델 확정 = 후보 생성 → 사장님 선정** — 시드를 바꿔가며 후보 얼굴 4~6장 생성, 1명 선정 후 canonical reference로 등록
  3. **VOV 벤치마크 = 레퍼런스 게시물 분석 → 프롬프트 반영** — 사용자가 제공할 VOV 게시물 3~5개에서 색감·배경·포즈·카메라·영상 템포·카피 톤을 분석해 템플릿에 스타일 언어로 반영. VOV 이미지 자체는 생성 모델에 주입하지 않음 (저작권·부정경쟁 리스크 회피)
  4. **GO/NO-GO = 파일럿 육안 평가** — 전속 모델 확정 후 실상품 1~2개로 화보 4장+릴스 1개 생성, VOV 레퍼런스와 나란히 사용자 육안 판정. 미달 시 원인별 개선 후 재파일럿
  5. **운영 규모 = 파일럿 후 결정** (초기 가이드: 주 2회 게시, 게시당 화보 1~2장+릴스 1개)
  6. **발행 = 담당자 수동 게시 유지** (PRD 범위 '등록 준비까지' 불변)
- **실행 순서**: ① 얼굴 고정 기술검증 (custom_reference_id 등록 경로 + soul/character 소규모 실증) → ② 후보 모델 생성·선정 → ③ 검수 UI 구현 (ADR-013) → ④ 파일럿 → GO/NO-GO
- **결과**: MCP 구독 비용 없이 기존 Platform API 크레딧으로 진행 가능성 확보. 기술검증 실패 시 대안(MCP 구독+Soul 학습)으로 회귀하는 분기점을 ①에 배치.

---

## ADR-015. 상품 원본 보존 = flux-2 image_urls 참조 생성 (soul/standard text2image 대체) ✅

- **일자**: 2026-07-09 (사용자 지시로 실증 후 반영)
- **컨텍스트**: "등록 상품과 화보가 다르게 나온다"(#3)의 근본 원인 확정. 기존 `agent3.generate_image`는 `higgsfield-ai/soul/standard`(text2image)에 프롬프트만 보내 상품 이미지를 참조로 안 넣었다 → 글자 설명만 보고 새 옷 생성. 실측: `soul`의 `custom_reference_id`는 **인물(얼굴) 참조**라 옷걸이 상품 사진을 넣으면 의상이 무시된다(랜덤 검정 코디 확인). 반면 **`flux-2` + `image_urls:[상품URL]`은 상품(디자인·색상·레이스 패턴·실루엣)을 보존**했다 (원본 흰 레이스 블라우스+차콜 데님 스커트가 도심 스트리트 화보로 재현, 육안 확인).
- **결정**:
  1. **화보 이미지 생성 = `flux-2`(image_urls 참조)** — `soul/standard` 텍스트 생성 대체. 상품 이미지를 `POST /files/generate-upload-url`(presigned)→PUT로 업로드해 public_url을 얻고 `image_urls`에 주입. `resolution:"2k"`, `aspect_ratio:"9:16"`. flux-2는 동기적으로 빠르게 완료돼 파이프라인 구조 유지(custom-references 비동기 완료 대기 불필요).
  2. **모델 얼굴 일관성(#4)은 별도 축** — flux-2 `image_urls`에 canonical 모델 참조 이미지를 함께 넣어 달성(`JBLANC_MODEL_REFERENCE_URL` 옵션). ADR-014의 얼굴 참조와 결합해 **상품+얼굴 2축 참조**로 발전.
  3. 영상(릴스)은 `higgsfield-ai/dop/standard`(image_url) 유지 — 화보를 image-to-video로 변환하므로 화보와 자동 일치.
- **실측 스키마**: 업로드 `/files/generate-upload-url`{content_type}→{public_url,upload_url}; 생성 `flux-2`{prompt(필수), image_urls[array URL], resolution∈1k|2k, aspect_ratio}. 알 수 없는 필드는 조용히 무시되므로 정확한 이름 필수.
- **결과**: 상품 보존 실증 완료(`storage/results/flux_tryon.jpg`, `flux_tryon_reel.mp4`). agent3 교체 + `higgsfield_client.upload_image()` 추가. 스텁 모드/테스트 무영향.

### ADR-015 후속: 전속 모델 canonical 참조 등록 완료 (ADR-014 ①② 이행) ✅

- **일자**: 2026-07-09 (후보 4장 생성 → 사용자가 **A** 선정)
- **모델**: 후보 A — 긴 생머리, 차분한 우아함. 원본 `storage/model/canonical_model.jpg` (중립 흰 티셔츠 + 무지 스튜디오 배경 = 의상 혼입 방지용)
- **등록 URL** (`.env`의 `JBLANC_MODEL_REFERENCE_URL`, .env는 gitignore이므로 여기에 보존):
  `https://d3snorpfx4xhv8.cloudfront.net/247c651d-ba0e-4286-a65a-c5b910db981c/d93a5211-dd77-4e67-a677-ba3ab177e674.jpeg`
- **동작**: agent3가 `image_urls = [상품 참조, 모델 참조]` 2장을 flux-2에 넣고, `apply_identity_lock()`이 "얼굴·헤어·정체성은 모델 참조에서만, 의상은 상품 참조에서" 절을 프롬프트에 덧붙인다. **이 절이 없으면 모델 참조의 흰 티셔츠가 결과물에 섞인다(실측).**
- **검증**: 실제 코드 경로로 생성 → `storage/results/canonical_test.jpg`. 얼굴=후보 A 동일, 의상=원본 레이스 블라우스+데님 스커트 보존, 모델 참조의 티셔츠·스튜디오 배경 미혼입, 배경=`concrete_architecture` 프리셋. **상품 보존(#3) + 모델 일관성(#4) 동시 달성.**
- **모델 교체 시**: 새 포트레이트를 업로드해 `JBLANC_MODEL_REFERENCE_URL`만 교체하면 된다 (코드 변경 불필요).

---

## 기록 규칙

- 새 결정이 기존 결정을 뒤집으면 기존 항목을 ❌ 폐기로 바꾸고 새 ADR에서 `(ADR-XXX 대체)`를 명시한다.
- 결정 전 반드시 사용자에게 질문한다는 프로젝트 규칙(CLAUDE.md)에 따라, 각 ADR은 사용자 승인 시점의 날짜를 기록한다.
