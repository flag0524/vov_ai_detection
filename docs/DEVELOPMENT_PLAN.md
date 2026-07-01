# 개발계획서 — JBLANC AI Fashion Marketing Automation System

> Development Plan
> 버전 1.0 · 작성일 2026-06-30

---

## 1. 개발 전략

핵심 리스크가 가장 큰 AI 일관성(모델 Identity 유지)과 상품 원본 보존을 먼저 검증한다. 이미지·영상 생성은 자체 추론 인프라 대신 Higgsfield MCP로 처리하고, 에이전트가 MCP를 직접 호출한다. 검증된 파이프라인 위에 영상·SNS 자동화·프론트엔드를 순차로 쌓는다.

각 단계는 독립적으로 검증 가능한 산출물을 갖는다.

## 2. 단계별 로드맵

### Phase 0 — 기반 셋업

- 모노레포 구조(`frontend`, `backend`, `agents`, `docs`) 구성.
- FastAPI 스켈레톤 + PostgreSQL + Object Storage + Job Queue 연결.
- 검증: 헬스체크 API와 더미 업로드/조회 동작.

### Phase 1 — 상품 분석 & AI 모델 생성 (핵심 검증)

- Agent 1 상품 분석으로 메타데이터 추출.
- Agent 3가 `higgsfield-soul-id`로 모델 1회 학습 후 `soul_reference_id` 저장·재사용.
- 검증: 동일 `model_id`(= 동일 Soul ID)로 여러 이미지 생성 시 얼굴 동일성 점수 확보.

### Phase 2 — 상품 원본 유지 이미지 생성

- Higgsfield product-photoshoot / image-to-image reference로 상품 원본 보존.
- Agent 2 프롬프트 자동 생성 연결.
- 검증: 상품 디자인·색상·패턴·로고 유지율(SSIM/임베딩) 기준 통과.

### Phase 3 — 영상 생성

- Agent 4가 `higgsfield-generate`(image-to-video)로 5~15초 릴스(9:16) 생성.
- 카메라 워킹·모션 옵션 적용.
- 검증: 프레임 간 얼굴 일관성, 배경 왜곡 점수.

### Phase 4 — SNS 콘텐츠 자동 생성

- Agent 5로 게시글 문구·해시태그·광고 카피 생성.
- 검증: 채널별 톤·해시태그 규칙 충족.

### Phase 5 — 프론트엔드 & 오케스트레이션

- Next.js: 상품 업로드 → 생성 요청 → 결과 확인 → 다운로드 → SNS 예약.
- MCP Orchestrator로 전체 파이프라인 end-to-end 연결.
- 검증: 상품 1건 업로드 → 화보·릴스·카피 자동 산출 시연.

### Phase 6 — 품질 검증 자동화 & 안정화

- Image/Video Quality Score 자동 평가 및 미달 재생성 루프.
- 브랜드 스타일 학습(JBLANC STYLE MODEL) 반영.
- 검증: 자동 평가 통과율 및 처리 시간 측정.

## 3. 마일스톤

| 마일스톤 | 산출물 | 완료 기준 |
| --- | --- | --- |
| M1 | 상품 분석 + 모델 Identity 유지 | 동일 모델 다중 이미지 생성 |
| M2 | 상품 원본 보존 이미지 | 유지율 기준 통과 |
| M3 | 릴스 영상 생성 | 5~15초 영상 + 일관성 점수 |
| M4 | SNS 콘텐츠 자동화 | 문구·해시태그·카피 산출 |
| M5 | End-to-End 플랫폼 | 업로드→콘텐츠 자동 산출 시연 |
| M6 | 품질 자동검증 안정화 | 자동 평가·재생성 루프 가동 |

## 4. 디렉터리 구조 (예정)

```
vov_ai_detection/
├── docs/                 # PRD, TRD, 개발계획서
├── frontend/             # Next.js
├── backend/              # FastAPI
│   ├── app/api/          # product / ai / sns 라우터
│   ├── app/services/     # 파이프라인·스토리지·큐
│   └── app/models/       # ORM 엔티티
├── agents/               # MCP Agent 1~5 (Higgsfield MCP 호출)
└── workers/              # Higgsfield MCP 호출 비동기 워커
```

## 5. 리스크 및 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| 모델 얼굴 일관성 저하 | 브랜드 신뢰도 | Soul ID 고정 + 자동 일관성 점수 |
| 상품 디자인 변형 | 상품 오인 | Higgsfield reference 제어 + 유지율 검증 회송 |
| 영상 품질 미달 | 광고 부적합 | 품질 점수 기준 미달 재생성 |
| 외부 MCP 비용·레이트리밋·지연 | 처리 속도·비용 | 비동기 큐 + 재시도·타임아웃 + 호출 모니터링 |

## 6. 검증 원칙

- 각 Phase는 자동 평가 점수 또는 시연으로 완료를 증명한다.
- 상품 원본 유지율과 모델 동일성은 모든 생성 단계의 게이트로 둔다.
- 기준 미달 산출물은 배포하지 않고 재생성 루프로 회송한다.
