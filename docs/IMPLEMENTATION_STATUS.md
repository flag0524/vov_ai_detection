# 구현 현황 보고서 — JBLANC AI Fashion (feature/review-ui)

- 작성일: 2026-07-15
- 브랜치: `feature/review-ui`
- 검증: 백엔드 pytest **61 passed**, 프론트 `next build`·`tsc --noEmit` 통과
- 관련 문서: [ADR.md](ADR.md) · [SCREEN_DESIGN.md](SCREEN_DESIGN.md) · [PRD.md](PRD.md) · [TRD.md](TRD.md)

이 문서는 최근 세션에서 확정·구현한 내용을 한 곳에 모은 현황 보고서다. 상세 설계는 위 문서를, 결정 근거는 ADR을 본다.

---

## 1. 한 줄 요약

상품 이미지를 올리면 **전속 모델(3인 중 선택)이 그 상품을 그대로 입은 화보**와 **릴스 영상**, **SNS 카피**를 생성하고, **검수(승인/재생성/폐기)**를 거쳐 **인스타 포맷으로 다운로드**하는 운영 루프가 완성됐다. 생성/검수/라이브러리 3탭 단일 페이지로 동작한다.

---

## 2. 핵심 문제 해결 (이번 세션의 성과)

### 2.1 "등록 상품·모델이 다르게 나온다" — 해결

| 항목 | 근본 원인 | 해결 |
|---|---|---|
| **상품 보존 (#3)** | 기존 `soul/standard`는 text2image라 상품 이미지를 참조로 안 넣고 프롬프트(글자)만 보냈다 → 다른 옷 생성 | **flux-2 `image_urls` 참조**로 전환. 상품 이미지를 업로드해 참조로 주입 (ADR-015) |
| **모델 얼굴 고정 (#4)** | Soul `custom_reference`는 얼굴 참조지 의상 참조가 아니고, flux-2는 custom_reference를 안 받음. LoRA는 자체 인프라 필요(ADR-001 위반) | **전속 모델 다각도 참조(정면·45도·측면)**를 flux-2 `image_urls`에 함께 주입. A/B 실측으로 얼굴 일치도 향상·상품 희석 없음 확인 |
| **네거티브 무효** | agent2가 `negative_prompt`를 만들었지만 agent3가 flux-2 페이로드에 안 실었다 | 배선 수정 + 회귀 테스트. 이후 의상 변형·비율·맨발·AI아티팩트 네거티브가 실제로 작동 |

### 2.2 생성 방식 (Higgsfield Platform REST, 실측 스키마)

```
① 상품 업로드   POST /files/generate-upload-url {content_type} → public_url 얻고 PUT
② 화보 생성     flux-2 {prompt, negative_prompt,
                        image_urls:[상품, 전속모델 정면·45도·측면],
                        aspect_ratio:"9:16", resolution:"2k"}
③ 릴스(이연)    higgsfield-ai/dop/standard {prompt, image_url(=화보)}  ← 검수 후 트리거
```

- 얼굴=전속 모델 참조, 상품=상품 참조 → **identity-lock 절**로 "얼굴은 모델 참조에서, 의상은 상품 참조에서, 티셔츠·스튜디오 배경 복사 금지"를 명시(안 하면 모델 참조의 흰 티셔츠가 혼입됨).
- Soul `custom-references`는 얼굴 참조 전용이라 사용하지 않는다.

### 2.3 실사 화보 프롬프트 템플릿 (사용자 지정)

`Subject → Action → Appearance → Background → Technical → Expression/Pose` 구조.
- **Appearance**: 한국인 표준 체형, 키 169~170cm, 7~7.5등신, NOT 9-head (AI 과장 비율 억제)
- **Action**: 카메라 쪽 자연스러운 보행, 발 미끄러짐 없음, 신발 착용(맨발 금지)
- **Technical**: 8k, 35mm 렌즈, 포토리얼, 원단 텍스처 극세부, NOT CGI
- **Negative**: 의상 변형(소매·넥라인·헴), 다리 늘어남, 맨발, AI 아티팩트, 만화/CGI 차단
- 브랜드명은 `BRAND_NAME` 상수(기본 **JBLANC**). VOV는 ADR-014대로 벤치마크로만 사용(생성물 주입 금지).

---

## 3. 화면 구현 현황

단일 페이지 3탭: **생성 / 검수 / 라이브러리**.

| ID | 화면 | 상태 | 내용 |
|---|---|---|---|
| SCR-001 | 생성 메인 | ✅ | 품번 자동채번, 카테고리 칩(상의/하의/원피스/아우터), 색상 팔레트 자동 추출, 소재·핏·스타일 담당자 입력, **전속 모델 3인 선택**, 배경 프리셋 10종+커스텀, 릴스 동작 선택, 원본↔화보 비교 |
| SCR-002 | 검수·재생성 | ✅ | 상태 탭(전체/검수대기/승인됨/폐기), 원본↔생성물 비교, SSIM, **승인/재생성(프롬프트 수정+크레딧 확인)/폐기**, 재생성 이력 |
| SCR-003 | 모델 관리 | ✅ | 전속 모델 3인(우아·모던 170 / 세련·시크 169 / 깨끗·내추럴 170), 카드 선택 피팅 |
| SCR-004 | 콘텐츠 라이브러리 | ✅ | 카테고리 탭, 카드 그리드, 상세(화보·릴스·SNS), **인스타 포맷 다운로드**, **캡션 복사** |

---

## 4. 백엔드 API

| 메서드·경로 | 용도 |
|---|---|
| `POST /product/upload` | 상품 업로드(+정보), 품번 자동채번 반환 |
| `POST /product/analyze-palette` | 색상 팔레트 자동 추출(PIL, 외부 API 없음) |
| `GET /ai/models` | 전속 모델 목록·기본값 (SCR-003) |
| `POST /pipeline/run` | 화보 + SNS 카피 생성 (영상 제외, `model_key`·`background`·`camera_motion`) |
| `POST /pipeline/video` | 검수 후 릴스 생성 (최신 화보 → image-to-video) |
| `GET /review/jobs?status=` | 검수 목록(원본 URL·화보·SSIM·상태·이력) |
| `PATCH /review/jobs/{id}` | 승인/폐기 (job.qa_status + Content.status 동시 전이) |
| `POST /review/jobs/{id}/regenerate` | 프롬프트 수정 재생성(이력 보존) |
| `GET /contents?category=` | 라이브러리 목록 |
| `GET /contents/{id}/export?format=` | 인스타 포맷(feed/reel/story) 리사이즈 다운로드 |
| `GET /storage/...` | 원본 상품 이미지 서빙(StaticFiles, ADR-013 ⑤) |

---

## 5. 확정된 아키텍처 결정 (ADR 요약)

- **ADR-001**: 자체 Diffusion/IP-Adapter/ControlNet/LoRA 인프라 미사용 → Higgsfield 사용. (유지)
- **ADR-011**: SSIM은 정보성 점수, 미달 시 manual_review 표시(자동 재생성/failed 없음).
- **ADR-012**: 상품 정보 담당자 직접 입력, 규칙 기반 템플릿, Anthropic 미사용.
- **ADR-013**: 영상을 검수 승인 이후로 이연. **이번에 ① 구현** — `/pipeline/run`은 화보+카피까지, 릴스는 `/pipeline/video`로 분리.
- **ADR-014**: 전속 가상 모델 운영(얼굴=참조 방식), VOV=벤치마크(주입 금지), 파일럿 GO/NO-GO.
- **ADR-015 (신규)**: 상품 보존 = flux-2 image_urls 참조 생성. 다각도 모델 참조로 얼굴 고정. 전속 모델 3인 레지스트리(`storage/model/registry.json`).

---

## 6. 검증 근거 (실측)

- **상품 보존**: 원본(흰 레이스 블라우스+차콜 데님 스커트)이 도심/지중해/테라스/콘크리트 배경 화보로 재현됨 (`storage/results/final_*.jpg`, `fit_*.jpg`).
- **모델 3인 피팅**: 같은 상품으로 3인 각각 얼굴 다르게, 상품 보존 유지.
- **네거티브 효과**: 긴소매 변형·맨발 결함이 네거티브 배선 수정 후 해소됨.
- **릴스 이연 E2E**: `POST /pipeline/video` 라이브 호출 → 6분 12초에 완료, `stub:false`, 실제 8.5MB 영상, 라이브러리 자동 연결 확인.
- **인스타 다운로드**: 실 DB 화보 → Feed 1080×1350 JPEG 200 OK.

> 주의: 영상(mp4) 동작의 자연스러움 최종 판정은 육안 확인이 필요하다(앱: 라이브러리 → 상품 → 릴스 재생).

---

## 7. 미비 사항 / 남은 과제

| 항목 | 현황 | 영향 |
|---|---|---|
| 비동기 큐(Redis) | 미도입, 동기 처리 | 생성 중 진행률 표시 없음. 릴스는 이연으로 완화했으나 화보도 1~2분 블로킹 |
| DB·스토리지 | SQLite + 로컬 파일 | PostgreSQL·S3 미전환. 구 스키마 job 필드 불일치는 코드로 방어만(정식 마이그레이션 없음) |
| 품번·카테고리 | 품번 비영속(표시용), 2차 세부 칩 미구현 | 라이브러리 영속 식별 필요 시 `Product.sku` 승격 |
| 검수 자동 게이트 | SSIM=정보성, 얼굴 유사도는 임베딩 입력 시에만 | 검수는 육안 판정 중심 |
| 프론트 테스트 | 없음(백엔드만 61 passed) | E2E 회귀 미보장 |
| 문서 정렬 | ADR·SCREEN_DESIGN 갱신됨 | PRD·TRD 일부 정렬 미확인 |
| 크레딧·계정 | 백엔드 Platform 계정만 크레딧 보유 | MCP 계정은 0. 크레딧 소진 시 스텁 강등 |

---

## 8. 운영 루프 (완성된 흐름)

```
상품 업로드 → 모델 3인 선택 → 배경/씨 선택 → 생성 시작(화보+카피, 빠름)
  → 검수(원본↔화보 비교, 승인/재생성/폐기)
  → 승인 화보로 릴스 생성(수 분)
  → 라이브러리(인스타 포맷 다운로드 + 캡션 복사) → 담당자 수동 게시
```
