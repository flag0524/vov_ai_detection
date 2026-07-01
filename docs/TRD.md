# TRD — JBLANC AI Fashion Marketing Automation System

> Technical Requirements Document
> 버전 2.0 · 작성일 2026-06-30
> 변경: 이미지/영상 생성을 자체 Diffusion → **Higgsfield MCP**로 확정. 에이전트가 MCP를 직접 호출, 얼굴 일관성은 **Soul ID** 기반.

---

## 1. 시스템 아키텍처 개요

```
[Next.js Frontend]
      │ REST / 업로드
      ▼
[FastAPI Backend] ── 작업(job) 라우팅 ──► [MCP Agent Orchestrator]
      │                                        │
      │                                        ├─ Agent 1: 상품 분석
      │                                        ├─ Agent 2: Prompt Engineer
      │                                        ├─ Agent 3: Fashion Model (Soul ID)
      │                                        ├─ Agent 4: Video Creator
      │                                        └─ Agent 5: Marketing
      │                                        │
      │                                        ▼ (MCP tool call)
      │                                 [Higgsfield MCP]
      │                                   ├─ higgsfield-soul-id (모델 학습)
      │                                   ├─ higgsfield-generate (이미지/영상)
      │                                   └─ higgsfield-product-photoshoot
      │
      ├─► [Object Storage] 상품 원본 / 결과물(이미지·영상)
      ├─► [Vector DB]      스타일 임베딩 / 검수용 얼굴 임베딩
      ├─► [RDB]            모델·상품·작업·콘텐츠 메타데이터
      └─► [Job Queue]      생성 작업 비동기 처리·상태 추적
```

핵심 변경점은 이미지·영상 생성을 자체 GPU 추론이 아니라 **Higgsfield MCP 호출**로 처리한다는 점이다. 따라서 백엔드는 GPU 워커 대신 **MCP 호출 작업의 비동기 오케스트레이션과 상태 관리**에 집중한다.

## 2. 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | Next.js (App Router), TypeScript |
| Backend | FastAPI (Python), Pydantic |
| 비동기 작업 | Celery / RQ + Redis (Job Queue) |
| 데이터베이스 | PostgreSQL (메타데이터) |
| 벡터 저장소 | pgvector 또는 Qdrant (스타일·검수 임베딩) |
| 스토리지 | S3 호환 Object Storage |
| 에이전트 | MCP 기반 Agent Orchestrator |
| 이미지/영상 생성 | **Higgsfield MCP** (Soul ID, Generate, Product Photoshoot) |
| 상품 분석 | Vision 모델 (카테고리·속성 추출) |

> 자체 Diffusion / IP Adapter / ControlNet 추론 인프라는 사용하지 않는다. 모델 일관성과 상품 반영은 Higgsfield의 Soul ID·reference·image-to-image 기능으로 구현한다.

## 3. Higgsfield MCP 매핑

| 요구 기능 | Higgsfield 기능 | 비고 |
| --- | --- | --- |
| 모델 얼굴 일관성(Identity 유지) | `higgsfield-soul-id` (Soul Character 학습 → `reference_id`) | 모델당 1회 학습, 이후 재사용 |
| 화보 이미지 생성 | `higgsfield-generate` (image, `--soul-id`) | Soul ID 주입으로 동일 인물 |
| 상품 기반/브랜드 화보 | `higgsfield-product-photoshoot` | 상품 reference 이미지 입력 |
| 영상(릴스/쇼츠) 생성 | `higgsfield-generate` (video, image-to-video) | 5~15초, 9:16 |

### 3.1 모델 일관성 — Soul ID

- 모델 생성 시 `higgsfield-soul-id`로 Soul Character를 1회 학습하고 반환된 `reference_id`를 `AIModel.soul_reference_id`에 저장한다.
- 모든 이미지·영상 생성은 해당 Soul ID를 `--soul-id`로 주입해 얼굴·체형·스타일 일관성을 유지한다.
- 모델 속성(`hair_style`, `age`, `mood`, `fashion_style`)은 프롬프트 고정 토큰으로 보조한다.

### 3.2 상품 원본 보존 (변경 금지)

- 상품 이미지를 `higgsfield-product-photoshoot` 또는 `higgsfield-generate`의 image-to-image / reference 입력으로 전달한다.
- 디자인·패턴·색상·로고·핏은 Higgsfield의 reference 제어로 보존하고, 생성 후 **상품 영역 유지율을 자체 검수**(SSIM/임베딩 유사도)한다.
- 기준 미달 시 재생성 큐로 회송한다.

## 4. MCP Agent 구성 (에이전트가 Higgsfield MCP 직접 호출)

| Agent | 역할 | 호출하는 MCP 기능 |
| --- | --- | --- |
| Agent 1 상품 분석 | 상품 이미지 분석·카테고리 분류 | Vision 분석 (Higgsfield 미사용) |
| Agent 2 Prompt Engineer | 생성 프롬프트 자동 작성 | — (프롬프트 산출) |
| Agent 3 Fashion Model | 동일 모델 유지·이미지 생성 | `higgsfield-soul-id`, `higgsfield-generate`, `higgsfield-product-photoshoot` |
| Agent 4 Video Creator | 이미지 → 영상 변환 | `higgsfield-generate` (image-to-video) |
| Agent 5 Marketing | SNS 문구·해시태그·카피 생성 | — (텍스트 산출) |

오케스트레이터는 단계별 산출물을 다음 Agent 입력으로 전달하고, 각 Higgsfield 호출은 `job_id`로 비동기 추적한다. 백엔드는 MCP를 직접 호출하지 않고 Agent에 작업을 위임한다.

## 5. API 명세 (초안)

### POST /product/upload — 상품 등록

요청: 상품 이미지(multipart).
응답: `product_id`, 분석된 상품 메타데이터.

### POST /ai/model/create — AI 모델 생성 (Soul ID 학습)

요청: 모델 속성(`hair_style`, `age`, `mood`, `fashion_style`), 학습용 이미지.
응답: `job_id`. 완료 시 `model_id`, `soul_reference_id`.

### POST /ai/image/generate — 이미지 생성

요청: `product_id`, `model_id`, 옵션(배경/무드).
응답: `job_id`(비동기). 완료 시 이미지 URL 목록.

### POST /ai/video/generate — 영상 생성

요청: `image_id`, 길이(5~15초), 카메라 옵션.
응답: `job_id`. 완료 시 영상 URL.

### POST /sns/content/create — SNS 콘텐츠 생성

요청: `image_id` / `video_id`, 톤·채널.
응답: 게시글 문구, 해시태그, 광고 카피.

### GET /jobs/{job_id} — 비동기 작업 상태 조회 (공통)

응답: `status`(queued|running|done|failed), 결과 참조.

## 6. 데이터 모델 (핵심 엔티티)

```
AIModel(model_id, soul_reference_id, body_style, hair_style, age, mood, fashion_style)
Product(product_id, name, category, color, material, silhouette, season, style, target_customer, image_ref)
GenerationJob(job_id, type[soul|image|video], product_id, model_id, status, mcp_call_ref, params, result_refs)
Content(content_id, source_ref, caption, hashtags, ad_copy, channel, status)
```

> 기존 `face_embedding`은 Higgsfield Soul ID로 대체된다. 단, **검수용 얼굴 임베딩**은 생성 결과의 동일성 점수 계산을 위해 Vector DB에 별도 보관한다.

## 7. 품질 검증 (자동 평가)

| 점수 | 계산 방식(초안) |
| --- | --- |
| Image Quality Score | 얼굴 임베딩 유사도(검수용) + 상품 영역 유지율(SSIM) + 브랜드 적합도 |
| Video Quality Score | 프레임 간 얼굴 일관성 + 배경 왜곡 감지 + 모션 자연스러움 |

기준 미달 산출물은 재생성 큐로 자동 회송한다. Higgsfield의 Virality Predictor(`brain_activity`)는 영상 콘텐츠의 후크/리텐션 점수 보조 지표로 활용할 수 있다.

## 8. 비기능 요구사항

- Higgsfield MCP 호출은 비동기 큐로 처리하고 재시도·타임아웃·실패 회송 정책을 둔다.
- MCP 인증 토큰 및 모델 `soul_reference_id`는 접근 제어 하에 보관한다.
- 원본/결과물은 Object Storage, 메타는 RDB가 관리한다.
- 외부 MCP 의존도가 높으므로 호출 비용·레이트리밋 모니터링을 둔다.
