# TRD — 제이블랑(JBLANC) AI Fashion Content Automation System

- 문서 버전: v1.1
- 작성일: 2026-07-02
- 변경 이력: v1.1 — **동작·표정 자연스러움(Naturalness) 검증 모듈** 및 관련 프롬프트/QA 스펙 추가

---

## 1. 시스템 아키텍처

```
[Frontend: 상품 업로드 UI]
        ↓
[Backend: Python FastAPI]
        ↓
[AI Layer]
 ├─ Vision Model (상품 분석)
 ├─ Prompt Generator
 ├─ Image Generator
 ├─ Video Generator (Higgsfield MCP)
 └─ Naturalness Validator (동작·표정 검증)  ← 신규
        ↓
[Storage]
 ├─ Vector DB (브랜드 스타일 / 모델 정보 / 상품 정보)
 └─ PostgreSQL (메타데이터, 생성 이력)
```

## 2. 기술 스택

| 레이어 | 기술 |
|---|---|
| Frontend | React (상품 업로드 UI) |
| Backend | Python FastAPI |
| AI 분석 | Vision Model (상품 이미지 분석) |
| 이미지 생성 | AI Image Generation API (identity reference 지원 모델) |
| 영상 생성 | Higgsfield MCP |
| 얼굴 검증 | Face embedding (InsightFace/ArcFace 계열) |
| 동작·표정 검증 | Pose estimation + Facial landmark 분석 (신규) |
| Vector DB | 모델/브랜드/상품 임베딩 저장 |
| RDB | PostgreSQL |
| 인프라 | Docker, 환경변수 관리, 구조화 Logging |

## 3. 데이터 모델 (핵심)

### models 테이블
```
model_id        VARCHAR PK   -- 예: JBLANC_MODEL_001
face_embedding  VECTOR       -- 얼굴 임베딩
face_features   JSONB        -- 얼굴 특징
hair_style      JSONB
body_type       JSONB
skin_tone       VARCHAR
mood            VARCHAR
pose_style      JSONB
created_at      TIMESTAMP
```

### generations 테이블
```
generation_id     UUID PK
product_id        FK
model_id          FK
type              ENUM(image, video)
prompt            TEXT
negative_prompt   TEXT
output_url        TEXT
identity_score    FLOAT   -- 얼굴 유사도
naturalness_score FLOAT   -- 동작·표정 자연스러움 점수 (신규)
qa_status         ENUM(pass, regenerate, manual_review)
created_at        TIMESTAMP
```

## 4. MCP Agent 스펙 — JBLANC_AI_CREATIVE_AGENT

### create_fashion_image()
- 입력: `product_image`, `model_id`, `style_prompt`
- 출력: `generated_image`
- 처리: 모델 ID의 얼굴/체형 정보 로드 → identity reference 적용 → 생성

### create_fashion_video()
- 입력: `image_reference`, `motion_prompt`, `camera_prompt`
- 출력: `fashion_video`
- motion_prompt에 자연스러움 지시어 필수 포함 (아래 §6 참조)

### validate_identity()
- Face embedding similarity 계산, threshold 0.85
- 미달 시 자동 재생성

### validate_naturalness() — 신규
- 기능: 생성 이미지/영상의 동작·표정 자연스러움 검증
- 이미지 검증:
  - Facial landmark 분석 → 표정 왜곡·비대칭·경직 검출
  - Pose estimation → 관절 각도 이상치, 손가락 개수/형태 검출
- 영상 검증:
  - 프레임 간 landmark 변화량 → 표정 급변(morphing)·얼굴 떨림 검출
  - Optical flow / pose sequence → 걷기 리듬, 보폭, 팔 스윙 자연스러움 평가
  - 관절 궤적 연속성 → 꺾임/순간이동 오류 검출
- 출력: `naturalness_score` (0~1), 세부 flag 목록
- 임계값: score < 0.8 → 자동 재생성, 0.8~0.9 → manual_review, ≥ 0.9 → pass

## 5. 이미지 생성 프롬프트 스펙

### 기본 Prompt Template
```
Create a premium fashion campaign image for JBLANC brand.

Model: Same female fashion model identity, consistent face,
natural Korean fashion model appearance.
Expression: natural relaxed expression, soft gaze,
subtle confident smile, lifelike facial detail.        ← 신규
Style: Luxury Korean fashion magazine style.
Product: [상품정보]
Scene: [배경 설명]
Lighting: Soft natural studio lighting.
Camera: 85mm fashion photography, high resolution, realistic texture.
Pose: Natural fashion pose, anatomically correct body,
natural weight distribution, relaxed hands.            ← 신규
Quality: Ultra realistic, professional fashion editorial,
commercial photography.
```

### Negative Prompt
```
different face, identity change, bad anatomy, extra fingers,
unnatural body, plastic skin, AI generated look, distorted clothing,
wrong product details,
-- 자연스러움 관련 (신규) --
stiff pose, unnatural facial expression, frozen face, awkward smile,
dead eyes, asymmetric distorted face, broken joints, distorted fingers,
unnatural neck angle, uncanny valley
```

## 6. 영상 생성 프롬프트 스펙

### Motion Prompt Template
```
Create cinematic fashion video.
A consistent AI fashion model wearing JBLANC product.
The model walks naturally in a luxury fashion space.

Camera movement: Slow cinematic tracking shot.
Motion: Natural human walking rhythm, realistic stride and arm swing,
natural hair movement, realistic clothing physics,
smooth continuous body motion.                          ← 강화
Facial expression: Consistent natural expression across frames,
soft lifelike micro-expressions, no expression morphing. ← 신규
Environment: Premium fashion boutique atmosphere.
Style: Korean fashion brand commercial.
```

### 영상 Negative Prompt (신규)
```
robotic movement, jerky motion, unnatural gait, sliding feet,
frame jitter, face morphing, twitching face, expression flickering,
limb distortion, teleporting body parts, frozen expression
```

## 7. API 설계 (요약)

| Method | Endpoint | 설명 |
|---|---|---|
| POST | /api/v1/products | 상품 업로드 + 메타정보 |
| POST | /api/v1/analyze/{product_id} | 상품 분석 실행 |
| POST | /api/v1/models | AI 모델 생성 (모델 ID 발급) |
| POST | /api/v1/generate/image | 이미지 생성 (model_id 지정) |
| POST | /api/v1/generate/video | 영상 생성 |
| POST | /api/v1/validate/identity | 얼굴 일관성 검증 |
| POST | /api/v1/validate/naturalness | 동작·표정 자연스러움 검증 (신규) |
| GET | /api/v1/contents/{product_id} | 인스타 콘텐츠 결과 조회 |

## 8. 품질 검증 파이프라인

```
생성 결과
  ↓
validate_identity()      -- 얼굴 유사도 ≥ 0.85
  ↓ pass
validate_naturalness()   -- 자연스러움 score ≥ 0.9  (신규)
  ↓ pass
상품 디테일 검증          -- 옷 왜곡/디테일 오류
  ↓ pass
Instagram Content Output (1080x1350 / 1080x1920)
```
- 어느 단계든 fail → Negative Prompt 보강 후 자동 재생성 (최대 3회) → 이후 manual_review 큐

## 9. 비기능 / 운영

- Docker Compose 기반 로컬/운영 환경 통일
- 환경변수: API 키, DB 접속, threshold 값 (identity/naturalness) 외부화
- Logging: 생성 요청~QA 결과까지 structured JSON 로그
- Error Handling: 외부 API 실패 시 retry(backoff), 실패 이력 DB 기록
- 테스트: 유닛(프롬프트 생성/검증 로직), 통합(파이프라인 E2E), QA threshold 회귀 테스트
