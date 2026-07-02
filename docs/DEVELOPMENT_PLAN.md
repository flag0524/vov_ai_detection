# 개발계획서 — 제이블랑(JBLANC) AI Fashion Content Automation System

- 문서 버전: v1.1
- 작성일: 2026-07-02
- 변경 이력: v1.1 — **동작·표정 자연스러움 검증(Naturalness QA)** 작업을 Phase 3/4에 반영

---

## 1. 개발 원칙

- Production 수준 코드: 모듈화, API 구조 설계, Docker 지원, 환경변수 관리, Logging, Error Handling, 테스트 코드 필수
- 구현 순서: Architecture 설계 → DB 설계 → Backend API → MCP Agent → AI Pipeline 연결 → Frontend → 테스트 → 배포

## 2. 단계별 계획

### Phase 0 — 기반 구축 (1주)
- 시스템 아키텍처 확정 (TRD 기준)
- PostgreSQL / Vector DB 스키마 설계 (naturalness_score 컬럼 포함)
- FastAPI 프로젝트 스캐폴딩, Docker Compose, 환경변수/로깅 셋업

### Phase 1 — 상품 분석 & 프롬프트 생성 (2주)
- 상품 이미지 업로드 API
- Vision Model 상품 분석 (의류 종류/소재/색상/디자인/스타일)
- 패션 컨셉 생성 + Prompt Engineering 모듈
  - 표정·포즈 자연스러움 지시어를 기본 프롬프트 템플릿에 내장
  - Negative Prompt 사전 구축 (identity + naturalness 항목 포함)
- 산출물: 분석 API, 프롬프트 생성기, 유닛 테스트

### Phase 2 — AI 모델 고정 시스템 (2주)
- 모델 ID 시스템 (JBLANC_MODEL_001 형식)
- 얼굴/헤어/체형/피부톤/분위기/포즈 스타일 저장 (Vector DB + PostgreSQL)
- validate_identity(): Face embedding similarity (threshold 0.85)
- 산출물: 모델 등록/호출 API, 얼굴 검증 모듈

### Phase 3 — 이미지 생성 + 자연스러움 검증 (3주)
- create_fashion_image() 구현 (identity reference 적용)
- **validate_naturalness() — 이미지** (신규 핵심 작업)
  - Facial landmark 기반 표정 왜곡/경직 검출
  - Pose estimation 기반 관절·손가락 이상 검출
  - naturalness_score 산출 및 threshold 기반 자동 재생성 (최대 3회)
- 품질 검증 파이프라인 연결: identity → naturalness → 상품 디테일
- Instagram Feed 이미지 출력 (1080x1350)
- 산출물: 이미지 생성 파이프라인 E2E, QA 리포트

### Phase 4 — 영상 생성 + 동작 자연스러움 검증 (3주)
- Higgsfield MCP 연동, create_fashion_video() 구현
- Motion/Camera Prompt 템플릿 (자연스러운 걷기·손동작·표정 지시어 포함)
- **validate_naturalness() — 영상** (신규 핵심 작업)
  - 프레임 간 표정 급변(morphing)·얼굴 떨림 검출
  - Optical flow / pose sequence 기반 걷기 리듬·보폭·팔 스윙 평가
  - 관절 궤적 연속성 검사
- Reel/Story 출력 (1080x1920)
- 산출물: 영상 생성 파이프라인 E2E, 동작 QA 모듈

### Phase 5 — 인스타그램 자동 배포 (2주)
- Caption/Hashtag/상품 설명 자동 생성
- 배포 스케줄링 및 Instagram 연동
- Frontend 업로드/검수 UI 완성 (QA fail 건 manual_review 화면 포함)
- 산출물: 전체 시스템 E2E, 운영 배포

## 3. 일정 요약

| Phase | 기간 | 핵심 산출물 |
|---|---|---|
| 0 | 1주 | 아키텍처, DB, 인프라 |
| 1 | 2주 | 상품 분석 + 프롬프트 생성 |
| 2 | 2주 | 모델 ID + 얼굴 고정 |
| 3 | 3주 | 이미지 생성 + 표정·포즈 QA |
| 4 | 3주 | 영상 생성 + 동작 QA |
| 5 | 2주 | 인스타 자동 배포 |
| 합계 | 13주 | |

## 4. 테스트 계획

- 유닛: 프롬프트 생성, 검증 로직(threshold 경계값 포함)
- 통합: 상품 업로드 → 콘텐츠 출력 E2E
- QA 회귀: identity_score / naturalness_score threshold 변경 시 회귀 테스트
- 육안 검수: 자연스러움 자동 검증과 사람 평가의 일치율 측정 → threshold 튜닝

## 5. 완료 기준 (Definition of Done)

1. 얼굴 일관성: similarity ≥ 0.85, 동일 인물 인식률 95% 이상
2. **동작·표정 자연스러움: naturalness_score ≥ 0.9, 부자연 검출률 5% 미만**
3. 상품 디테일 왜곡 없음
4. 상품 업로드만으로 피드/릴스/스토리 + 캡션/해시태그 자동 생성
5. Docker 환경에서 전체 파이프라인 재현 가능, 테스트 커버리지 확보
