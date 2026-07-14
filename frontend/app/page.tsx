// 상품 업로드 → AI 생성 파이프라인 실행 → 화보/영상/SNS 카피 결과 확인 화면 (JBLANC 다크 UI)
"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type PipelineResult = {
  product_id: string;
  product_meta: Record<string, unknown>;
  model_id: string;
  soul_reference_id: string;
  prompt: string;
  image_url: string;
  quality: {
    ssim_score: number;
    product_pass: boolean;
    overall_pass: boolean;
    action: string;
  };
  video_url: string | null; // ADR-013 — 영상은 화보 확인 후 별도 생성
  camera_motion?: string;
  model_key?: string;
  model_name?: string;
  sns: {
    caption: string;
    hashtags: string[];
    ad_copy: string;
  };
  stubs: { image: boolean; video: boolean };
};

type Stage = "idle" | "uploading" | "generating" | "done" | "error";

// SCREEN_DESIGN §2.6 — 배경/씨 프리셋 (백엔드 agent2 PRESET_SCENES 키와 일치)
const BG_PRESETS = [
  ["studio_white", "스튜디오 화이트"],
  ["city_street", "시티 스트리트"],
  ["cafe", "카페 · 인테리어"],
  ["nature", "자연 · 아웃도어"],
  ["minimal_color", "미니멀 컬러"],
  // 여름 · 미니멀 · 모던 테마 (VOV 벤치마크 톤)
  ["luxury_terrace", "도심 럭셔리 테라스"],
  ["mediterranean", "지중해풍 미니멀"],
  ["resort_poolside", "리조트 풀사이드"],
  ["stone_courtyard", "화이트 스톤 코트야드"],
  ["concrete_architecture", "선드렌치드 콘크리트"],
] as const;

// SCREEN_DESIGN §2.5 #5 — 자연스러운 동작 연출 (백엔드 agent4 CAMERA_MOTION_PROMPTS 키와 일치)
const CAMERA_MOTIONS = [
  ["dolly_in", "다가가기"],
  ["dolly_out", "멀어지기"],
  ["orbit", "회전"],
  ["pan", "좌우 이동"],
  ["static", "정적(미세 동작)"],
] as const;

// 기본 정보 (담당자 입력)
const BASIC_FIELDS = [
  ["name", "상품명 (예: 네이비 트위드 재킷)"],
  ["target_customer", "타깃 고객"],
] as const;

// 카테고리 (상의/하의 구분) → 품번 코드. 백엔드 CATEGORY_CODES와 일치.
const CATEGORIES = [
  ["상의", "TOP"],
  ["하의", "BTM"],
  ["원피스", "OPS"],
  ["아우터", "OUT"],
] as const;

// AI 분석 패널의 속성 (색상은 자동 추출, 나머지는 담당자 입력 — ADR-012)
const ATTR_FIELDS = [
  ["material", "소재·텍스처 (예: 코튼 데님)"],
  ["silhouette", "핏·실루엣 (예: A라인 맥시)"],
  ["style", "스타일 무드 (럭셔리/캐주얼…)"],
] as const;

type PaletteColor = { hex: string; ratio: number };

// SCR-002 검수 대상 (GET /review/jobs)
type ReviewJob = {
  job_id: string;
  product_id: string;
  product_name: string | null;
  category: string | null;
  original_url: string | null;
  image_url: string | null;
  ssim: number | null;
  qa_status: string | null;
  attempts: number;
  history: { image_url: string; ssim: number | null; at: string }[];
  prompt: string | null;
  scene: string | null;
};

const QA_TABS = [
  ["", "전체"],
  ["manual_review", "검수대기"],
  ["approved", "승인됨"],
  ["discarded", "폐기"],
] as const;

// 전속 모델 (GET /ai/models) — 다각도 참조로 얼굴이 고정된다
type FashionModel = {
  key: string;
  name: string;
  height_cm: number;
  mood: string;
  thumbnail_url: string;
};

// SCREEN_DESIGN §5 — 콘텐츠 라이브러리 항목 (GET /contents)
type LibraryItem = {
  product_id: string;
  name: string | null;
  category: string | null;
  image_url: string | null;
  video_url: string | null;
  qa_status: string | null;
  ssim: number | null;
  caption: string | null;
  hashtags: string[];
  ad_copy: string | null;
};

// 다크 UI 공통 클래스
const CHIP_ON = "border-violet-500 bg-violet-500/15 text-violet-200";
const CHIP_OFF =
  "border-[#33333c] text-zinc-400 hover:border-zinc-600 hover:text-zinc-300";
const INPUT_CLS =
  "rounded-lg border border-[#33333c] bg-[#1b1b1f] px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-violet-500 focus:outline-none";
const SUBCARD =
  "flex flex-col gap-2 rounded-xl border border-[#33333c] bg-[#1b1b1f] p-3";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  // 상품 정보 직접 입력 (ADR-012 — Vision 자동 분석 대신 담당자 입력)
  const [info, setInfo] = useState({
    name: "",
    category: "",
    color: "",
    material: "",
    silhouette: "",
    style: "",
    target_customer: "",
  });
  // AI 이미지 분석 — 색상 팔레트 자동 추출 (외부 API 없음, ADR-012 준수)
  const [palette, setPalette] = useState<PaletteColor[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  // 품번 — 업로드 시 카테고리 코드로 자동 채번 (표시용)
  const [sku, setSku] = useState<string | null>(null);
  // 배경/씨 선택 (모델·상품은 고정, 배경만 변경)
  const [bgPreset, setBgPreset] = useState<string>("studio_white");
  const [bgCustom, setBgCustom] = useState("");
  // 릴스 카메라 동작 (자연스러운 연출 제어, #5)
  const [camMotion, setCamMotion] = useState<string>("dolly_in");
  // 모델 고정: 첫 생성의 모델을 세션 내 재사용해 동일 Soul ID 유지 (#4)
  const [modelId, setModelId] = useState<string | null>(null);
  // 전속 모델 선택 — 선택한 모델의 다각도 참조로 피팅한다
  const [models, setModels] = useState<FashionModel[]>([]);
  const [modelKey, setModelKey] = useState<string>("");
  // 릴스는 화보 확인 후 별도 생성 (ADR-013) — 수 분 걸린다
  const [reelUrl, setReelUrl] = useState<string | null>(null);
  const [reelStage, setReelStage] = useState<"idle" | "running" | "error">("idle");

  async function handleGenerateReel() {
    if (!result) return;
    setReelStage("running");
    try {
      const res = await fetch(`${API_BASE}/pipeline/video`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_id: result.product_id,
          camera_motion: camMotion,
        }),
      });
      if (!res.ok) throw new Error(`릴스 생성 실패 (${res.status})`);
      const data = await res.json();
      setReelUrl(data.video_url);
      setReelStage("idle");
    } catch {
      setReelStage("error");
    }
  }

  useEffect(() => {
    fetch(`${API_BASE}/ai/models`)
      .then((r) => (r.ok ? r.json() : { models: [], default: "" }))
      .then((d) => {
        setModels(d.models ?? []);
        setModelKey((prev) => prev || d.default || "");
      })
      .catch(() => setModels([]));
  }, []);
  // 뷰 전환 (생성 / 검수 / 라이브러리) + 라이브러리 상태
  const [view, setView] = useState<"create" | "review" | "library">("create");
  // SCR-002 검수
  const [reviewJobs, setReviewJobs] = useState<ReviewJob[]>([]);
  const [qaTab, setQaTab] = useState<string>("");
  const [reviewLoading, setReviewLoading] = useState(false);
  const [picked, setPicked] = useState<ReviewJob | null>(null);
  const [editPrompt, setEditPrompt] = useState("");
  const [busyAction, setBusyAction] = useState(false);

  async function loadReview(tab: string) {
    setReviewLoading(true);
    try {
      const url = tab
        ? `${API_BASE}/review/jobs?status=${encodeURIComponent(tab)}`
        : `${API_BASE}/review/jobs`;
      const res = await fetch(url);
      setReviewJobs(res.ok ? ((await res.json()).items ?? []) : []);
    } catch {
      setReviewJobs([]);
    } finally {
      setReviewLoading(false);
    }
  }

  useEffect(() => {
    if (view === "review") loadReview(qaTab);
  }, [view, qaTab]);

  async function decide(job: ReviewJob, action: "approve" | "discard") {
    setBusyAction(true);
    try {
      await fetch(`${API_BASE}/review/jobs/${job.job_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      setPicked(null);
      await loadReview(qaTab);
    } finally {
      setBusyAction(false);
    }
  }

  async function regenerate(job: ReviewJob) {
    if (!confirm("재생성은 크레딧을 소모합니다. 진행할까요?")) return;
    setBusyAction(true);
    try {
      const res = await fetch(`${API_BASE}/review/jobs/${job.job_id}/regenerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: editPrompt.trim() || null }),
      });
      if (res.ok) {
        await loadReview(qaTab);
        const fresh = await fetch(`${API_BASE}/review/jobs`).then((r) => r.json());
        setPicked(
          (fresh.items ?? []).find((j: ReviewJob) => j.job_id === job.job_id) ?? null,
        );
      }
    } finally {
      setBusyAction(false);
    }
  }
  const [library, setLibrary] = useState<LibraryItem[]>([]);
  const [libCategory, setLibCategory] = useState<string>("");
  const [libLoading, setLibLoading] = useState(false);
  const [selected, setSelected] = useState<LibraryItem | null>(null);

  useEffect(() => {
    if (view !== "library") return;
    setLibLoading(true);
    const url = libCategory
      ? `${API_BASE}/contents?category=${encodeURIComponent(libCategory)}`
      : `${API_BASE}/contents`;
    fetch(url)
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setLibrary(d.items ?? []))
      .catch(() => setLibrary([]))
      .finally(() => setLibLoading(false));
  }, [view, libCategory]);

  function onPickFile(f: File | null) {
    setFile(f);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return f ? URL.createObjectURL(f) : null;
    });
    setPalette([]);
    setSku(null);
    if (f) analyzePalette(f);
  }

  // 업로드 이미지에서 색상 팔레트만 자동 추출 (소재·핏·스타일은 담당자 입력)
  async function analyzePalette(f: File) {
    setAnalyzing(true);
    try {
      const form = new FormData();
      form.append("file", f);
      const res = await fetch(`${API_BASE}/product/analyze-palette`, {
        method: "POST",
        body: form,
      });
      if (res.ok) {
        const data = await res.json();
        setPalette(data.palette ?? []);
      }
    } catch {
      // 분석 실패는 생성 흐름을 막지 않는다 (색상은 참고용)
    } finally {
      setAnalyzing(false);
    }
  }

  const busy = stage === "uploading" || stage === "generating";

  async function handleGenerate() {
    if (!file) return;
    setError(null);
    setResult(null);
    setReelUrl(null);
    setReelStage("idle");

    try {
      setStage("uploading");
      const form = new FormData();
      form.append("file", file);
      Object.entries(info).forEach(([key, value]) => {
        if (value.trim()) form.append(key, value.trim());
      });
      const uploadRes = await fetch(`${API_BASE}/product/upload`, {
        method: "POST",
        body: form,
      });
      if (!uploadRes.ok) throw new Error(`업로드 실패 (${uploadRes.status})`);
      const uploaded = await uploadRes.json();
      const { product_id } = uploaded;
      if (uploaded.sku) setSku(uploaded.sku);

      setStage("generating");
      const pipelineRes = await fetch(`${API_BASE}/pipeline/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_id,
          background: { preset: bgPreset, custom: bgCustom.trim() },
          camera_motion: camMotion,
          ...(modelKey ? { model_key: modelKey } : {}),
          ...(modelId ? { model_id: modelId } : {}),
        }),
      });
      if (!pipelineRes.ok) throw new Error(`생성 실패 (${pipelineRes.status})`);
      const data: PipelineResult = await pipelineRes.json();

      setResult(data);
      // 이후 생성은 같은 모델(Soul ID)을 재사용해 모델 동일성 유지 (#4)
      setModelId(data.model_id);
      setStage("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStage("error");
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center">
      <main className="flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
        {/* 상단 브랜드 바 */}
        <div className="flex items-center justify-between">
          <div className="flex items-baseline gap-2.5">
            <span className="text-[13px] font-bold tracking-[0.14em] text-zinc-100">
              JBLANC
            </span>
            <span className="text-[10px] uppercase tracking-[0.28em] text-zinc-500">
              AI Fashion
            </span>
          </div>
          <div className="flex items-center gap-2">
            {view === "create" &&
              result &&
              (result.stubs.image || result.stubs.video) && (
                <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-300">
                  STUB 모드
                </span>
              )}
            <div className="flex rounded-full border border-[#2a2a31] bg-[#141417] p-0.5 text-xs">
              {(
                [
                  ["create", "생성"],
                  ["review", "검수"],
                  ["library", "라이브러리"],
                ] as const
              ).map(([v, label]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setView(v)}
                  className={`rounded-full px-3 py-1 transition-colors ${
                    view === v
                      ? "bg-violet-600 text-white"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {view === "create" && (
        <>
        <header>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-50">
            콘텐츠 생성
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            상품 이미지를 업로드하면 화보·릴스·SNS 카피를 자동 생성합니다 · 인스타그램 발행 준비
          </p>
        </header>

        {/* 상품 등록 카드 */}
        <section className="rounded-2xl border border-[#2a2a31] bg-[#141417] p-5">
          <div className="mb-4 flex items-center gap-2.5">
            <span className="grid h-5 w-5 place-items-center rounded-full bg-violet-500/15 text-[11px] font-bold text-violet-300">
              1
            </span>
            <span className="text-[15px] font-semibold text-zinc-100">상품 등록</span>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            {/* 상품 이미지 프리뷰 */}
            <div className="sm:w-40 sm:shrink-0">
              <div className="flex aspect-[3/4] items-center justify-center overflow-hidden rounded-xl border border-[#2a2a31] bg-[#17171b]">
                {previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={previewUrl}
                    alt="상품 미리보기"
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="px-3 text-center text-xs text-zinc-500">
                    이미지를 업로드하세요
                  </span>
                )}
              </div>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
                className="mt-2 w-full text-xs text-zinc-400 file:mr-2 file:rounded-full file:border-0 file:bg-violet-600 file:px-3 file:py-1.5 file:text-xs file:text-white hover:file:bg-violet-500"
              />
            </div>

            {/* 입력 필드 */}
            <div className="flex flex-1 flex-col gap-3">
              {/* 품번 (카테고리 코드 기반 자동 채번) */}
              <div className="flex items-center justify-between">
                <div className="flex items-baseline gap-2">
                  <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">
                    품번
                  </span>
                  <span className="font-mono text-lg font-semibold text-zinc-100">
                    {sku ??
                      `JBL-${
                        CATEGORIES.find(([label]) => label === info.category)?.[1] ??
                        "GEN"
                      }-•••`}
                  </span>
                  <span className="rounded bg-[#232329] px-1.5 py-0.5 text-[9px] tracking-[0.1em] text-zinc-400">
                    AUTO
                  </span>
                </div>
                {!sku && (
                  <span className="text-[11px] text-zinc-500">생성 시 자동 채번</span>
                )}
              </div>

              {/* 카테고리 (상의/하의 구분) */}
              <div>
                <span className="mb-1.5 block text-[10px] uppercase tracking-[0.16em] text-zinc-500">
                  카테고리
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {CATEGORIES.map(([label, code]) => (
                    <button
                      key={label}
                      type="button"
                      onClick={() =>
                        setInfo((prev) => ({
                          ...prev,
                          category: prev.category === label ? "" : label,
                        }))
                      }
                      className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                        info.category === label ? CHIP_ON : CHIP_OFF
                      }`}
                    >
                      {label} {code}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {BASIC_FIELDS.map(([key, placeholder]) => (
                  <input
                    key={key}
                    type="text"
                    placeholder={placeholder}
                    value={info[key]}
                    onChange={(e) => setInfo({ ...info, [key]: e.target.value })}
                    className={INPUT_CLS}
                  />
                ))}
              </div>

              {/* AI 이미지 분석 (색상 자동 추출 + 담당자 입력 속성) */}
              <div className={SUBCARD}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-zinc-300">AI 이미지 분석</span>
                  <span className="text-[11px] text-zinc-500">
                    {analyzing
                      ? "색상 분석 중..."
                      : palette.length
                        ? "색상 자동 · 나머지 담당자 입력"
                        : "이미지 업로드 시 색상 자동 추출"}
                  </span>
                </div>

                {/* 색상 팔레트 (자동) */}
                <div className="flex items-center gap-2">
                  <span className="w-16 shrink-0 text-[11px] text-zinc-500">색상 팔레트</span>
                  {palette.length ? (
                    <div className="flex flex-wrap items-center gap-1.5">
                      {palette.map((c) => (
                        <span
                          key={c.hex}
                          title={`${c.hex} · ${Math.round(c.ratio * 100)}%`}
                          className="flex items-center gap-1 rounded-md border border-[#33333c] px-1.5 py-1"
                        >
                          <span
                            className="h-4 w-4 rounded-sm"
                            style={{ backgroundColor: c.hex }}
                          />
                          <span className="font-mono text-[10px] text-zinc-400">
                            {c.hex}
                          </span>
                        </span>
                      ))}
                      <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] text-violet-300">
                        자동
                      </span>
                    </div>
                  ) : (
                    <span className="text-[11px] text-zinc-600">—</span>
                  )}
                </div>

                {/* 담당자 입력 속성 */}
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    placeholder="색상명 (예: 차콜 워시드)"
                    value={info.color}
                    onChange={(e) => setInfo({ ...info, color: e.target.value })}
                    className={INPUT_CLS}
                  />
                  {ATTR_FIELDS.map(([key, placeholder]) => (
                    <input
                      key={key}
                      type="text"
                      placeholder={placeholder}
                      value={info[key]}
                      onChange={(e) => setInfo({ ...info, [key]: e.target.value })}
                      className={INPUT_CLS}
                    />
                  ))}
                </div>
              </div>

              {/* 전속 모델 선택 — 선택한 모델로 피팅 */}
              {models.length > 0 && (
                <div className={SUBCARD}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-zinc-300">전속 모델</span>
                    <span className="text-[11px] text-zinc-500">
                      선택한 모델로 피팅 · 얼굴 고정
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {models.map((m) => (
                      <button
                        key={m.key}
                        type="button"
                        onClick={() => setModelKey(m.key)}
                        className={`flex flex-col overflow-hidden rounded-lg border text-left transition-colors ${
                          modelKey === m.key
                            ? "border-violet-500 ring-1 ring-violet-500/40"
                            : "border-[#33333c] hover:border-zinc-600"
                        }`}
                      >
                        <div className="aspect-[3/4] overflow-hidden bg-[#17171b]">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={m.thumbnail_url}
                            alt={m.name}
                            className="h-full w-full object-cover"
                          />
                        </div>
                        <div className="px-2 py-1.5">
                          <div
                            className={`truncate text-[11px] font-medium ${
                              modelKey === m.key ? "text-violet-200" : "text-zinc-300"
                            }`}
                          >
                            {m.name}
                          </div>
                          <div className="text-[10px] text-zinc-500">{m.height_cm}cm</div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* 배경 / 씬 */}
              <div className={SUBCARD}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-zinc-300">배경 / 씬</span>
                  <span className="flex items-center gap-1.5 text-[11px] text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    모델·상품 고정 · 배경만 변경
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {BG_PRESETS.map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setBgPreset(key)}
                      className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                        bgPreset === key ? CHIP_ON : CHIP_OFF
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <input
                  type="text"
                  placeholder="커스텀 배경 (예: 노을 지는 한강 산책로, 골든아워) — 입력 시 우선 적용"
                  value={bgCustom}
                  onChange={(e) => setBgCustom(e.target.value)}
                  className={INPUT_CLS}
                />
              </div>

              {/* 릴스 동작 연출 */}
              <div className={SUBCARD}>
                <span className="text-xs font-medium text-zinc-300">릴스 동작 연출</span>
                <div className="flex flex-wrap gap-1.5">
                  {CAMERA_MOTIONS.map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setCamMotion(key)}
                      className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                        camMotion === key ? CHIP_ON : CHIP_OFF
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 모델 고정 상태 */}
              <div className="flex items-center justify-between rounded-xl border border-[#33333c] bg-[#1b1b1f] px-3 py-2 text-xs">
                {modelId ? (
                  <>
                    <span className="text-zinc-400">
                      🔒 모델 고정됨 · {modelId.slice(0, 8)} (같은 Soul ID 재사용)
                    </span>
                    <button
                      type="button"
                      onClick={() => setModelId(null)}
                      className="text-violet-300 underline underline-offset-2 hover:text-violet-200"
                    >
                      새 모델로
                    </button>
                  </>
                ) : (
                  <span className="text-zinc-500">
                    첫 생성 시 모델이 고정되어 이후 동일 모델로 유지됩니다
                  </span>
                )}
              </div>

              <button
                onClick={handleGenerate}
                disabled={!file || busy}
                className="mt-1 self-start rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-violet-500 disabled:opacity-40"
              >
                {stage === "uploading" && "업로드 중..."}
                {stage === "generating" && "생성 중..."}
                {(stage === "idle" || stage === "done" || stage === "error") &&
                  "생성 시작"}
              </button>
              {error && <p className="text-sm text-red-400">{error}</p>}
            </div>
          </div>
        </section>

        {/* 결과 */}
        {result && (
          <section className="flex flex-col gap-4 rounded-2xl border border-[#2a2a31] bg-[#141417] p-5">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-full border border-violet-500/40 bg-violet-500/10 px-3 py-1 text-violet-200">
                👤 {result.model_name ?? "전속 모델"}
              </span>
              <span className="rounded-full border border-[#33333c] bg-[#1b1b1f] px-3 py-1 text-zinc-300">
                🎬{" "}
                {CAMERA_MOTIONS.find(([k]) => k === result.camera_motion)?.[1] ??
                  result.camera_motion}
              </span>
            </div>

            <div className="border-t border-[#2a2a31] pt-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-zinc-100">화보 이미지</h2>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-[11px] ${
                    result.quality.overall_pass
                      ? "bg-emerald-500/15 text-emerald-300"
                      : "bg-amber-500/15 text-amber-300"
                  }`}
                >
                  SSIM {result.quality.ssim_score} ·{" "}
                  {result.quality.overall_pass ? "통과" : "검수 필요"}
                </span>
              </div>

              {/* 원본 상품 ↔ 생성 화보 비교 (상품 유지 여부 확인) */}
              <div className="mt-3 grid grid-cols-2 gap-3">
                <figure className="flex flex-col gap-1">
                  <div className="flex aspect-[3/4] items-center justify-center overflow-hidden rounded-lg border border-[#2a2a31] bg-[#17171b]">
                    {previewUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={previewUrl}
                        alt="등록 상품 원본"
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <span className="text-xs text-zinc-600">원본 없음</span>
                    )}
                  </div>
                  <figcaption className="text-center text-[11px] text-zinc-500">
                    등록 상품(원본)
                  </figcaption>
                </figure>
                <figure className="flex flex-col gap-1">
                  <div className="flex aspect-[3/4] items-center justify-center overflow-hidden rounded-lg border border-[#2a2a31] bg-[#17171b]">
                    {result.stubs.image ? (
                      <span className="px-3 text-center text-[11px] text-amber-300/80">
                        스텁 이미지<br />(실제 생성물 아님)
                      </span>
                    ) : (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={result.image_url}
                        alt="생성 화보"
                        className="h-full w-full object-cover"
                      />
                    )}
                  </div>
                  <figcaption className="text-center text-[11px] text-zinc-500">
                    생성 화보
                  </figcaption>
                </figure>
              </div>
              <p className="mt-2 break-all text-[11px] text-zinc-600">
                {result.image_url}
              </p>
            </div>

            {/* 릴스 — 화보를 확인한 뒤 생성 (ADR-013) */}
            <div className="border-t border-[#2a2a31] pt-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-zinc-100">릴스 영상</h2>
                {!reelUrl && (
                  <button
                    type="button"
                    onClick={handleGenerateReel}
                    disabled={reelStage === "running"}
                    className="rounded-lg bg-violet-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-violet-500 disabled:opacity-40"
                  >
                    {reelStage === "running" ? "생성 중... (수 분)" : "이 화보로 릴스 생성"}
                  </button>
                )}
              </div>

              {reelUrl ? (
                <>
                  <video
                    src={reelUrl}
                    controls
                    className="mt-2 w-full max-w-xs rounded-lg border border-[#2a2a31]"
                  />
                  <p className="mt-2 break-all text-[11px] text-zinc-600">{reelUrl}</p>
                </>
              ) : reelStage === "error" ? (
                <p className="mt-2 text-sm text-red-400">
                  릴스 생성에 실패했습니다. 다시 시도해 주세요.
                </p>
              ) : (
                <p className="mt-2 text-[11px] text-zinc-500">
                  화보가 마음에 들면 릴스를 생성하세요. 영상은 크레딧이 비싸고 수 분 걸려,
                  화보 확인 후에만 만듭니다.
                </p>
              )}
            </div>

            <div className="border-t border-[#2a2a31] pt-4">
              <h2 className="text-base font-semibold text-zinc-100">SNS 카피</h2>
              <p className="mt-1 text-sm text-zinc-200">{result.sns.caption}</p>
              <p className="mt-1 text-sm text-violet-300">
                {result.sns.hashtags.join(" ")}
              </p>
              <p className="mt-1 text-sm font-medium text-zinc-100">
                {result.sns.ad_copy}
              </p>
            </div>
          </section>
        )}
        </>
        )}

        {/* SCR-002 검수 — 원본↔생성물 비교, 승인/재생성/폐기 */}
        {view === "review" && (
          <section className="flex flex-col gap-4">
            <header>
              <h1 className="text-2xl font-bold tracking-tight text-zinc-50">검수</h1>
              <p className="mt-1 text-sm text-zinc-400">
                원본과 생성 화보를 비교해 승인·재생성·폐기합니다. 승인된 건만 배포 준비로 넘어갑니다.
              </p>
            </header>

            <div className="flex flex-wrap gap-1.5">
              {QA_TABS.map(([key, label]) => (
                <button
                  key={key || "all"}
                  type="button"
                  onClick={() => {
                    setQaTab(key);
                    setPicked(null);
                  }}
                  className={`rounded-full border px-3.5 py-1 text-xs transition-colors ${
                    qaTab === key ? CHIP_ON : CHIP_OFF
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {reviewLoading ? (
              <p className="py-10 text-center text-sm text-zinc-500">불러오는 중...</p>
            ) : reviewJobs.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#2a2a31] py-14 text-center text-sm text-zinc-400">
                검수할 화보가 없습니다.
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {reviewJobs.map((j) => (
                  <button
                    key={j.job_id}
                    type="button"
                    onClick={() => {
                      setPicked(j);
                      setEditPrompt(j.prompt ?? "");
                    }}
                    className={`flex flex-col overflow-hidden rounded-xl border text-left transition-colors ${
                      picked?.job_id === j.job_id
                        ? "border-violet-500"
                        : "border-[#2a2a31] hover:border-zinc-600"
                    }`}
                  >
                    <div className="aspect-[3/4] overflow-hidden bg-[#17171b]">
                      {j.image_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={j.image_url}
                          alt="화보"
                          className="h-full w-full object-cover"
                        />
                      )}
                    </div>
                    <div className="flex flex-col gap-1 p-2">
                      <span className="truncate text-[11px] text-zinc-200">
                        {j.product_name || "이름 없음"}
                      </span>
                      <span
                        className={`w-fit rounded px-1.5 py-0.5 text-[10px] ${
                          j.qa_status === "approved"
                            ? "bg-emerald-500/15 text-emerald-300"
                            : j.qa_status === "discarded"
                              ? "bg-red-500/15 text-red-300"
                              : "bg-amber-500/15 text-amber-300"
                        }`}
                      >
                        {j.qa_status === "approved"
                          ? "승인됨"
                          : j.qa_status === "discarded"
                            ? "폐기"
                            : "검수대기"}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {/* 상세 — 비교 뷰 + QA + 판정 */}
            {picked && (
              <div className="flex flex-col gap-4 rounded-2xl border border-[#2a2a31] bg-[#141417] p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-zinc-100">
                    {picked.product_name || "화보 검수"}
                  </h2>
                  <span className="text-xs text-zinc-500">
                    {picked.attempts}차 생성 · SSIM {picked.ssim ?? "—"}
                  </span>
                </div>

                {/* 원본 ↔ 생성물 비교 */}
                <div className="grid grid-cols-2 gap-3">
                  <figure className="flex flex-col gap-1">
                    <div className="flex aspect-[3/4] items-center justify-center overflow-hidden rounded-lg border border-[#2a2a31] bg-[#17171b]">
                      {picked.original_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={`${API_BASE}${picked.original_url}`}
                          alt="원본 상품"
                          className="h-full w-full object-contain"
                        />
                      )}
                    </div>
                    <figcaption className="text-center text-[11px] text-zinc-500">
                      원본 상품
                    </figcaption>
                  </figure>
                  <figure className="flex flex-col gap-1">
                    <div className="flex aspect-[3/4] items-center justify-center overflow-hidden rounded-lg border border-[#2a2a31] bg-[#17171b]">
                      {picked.image_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={picked.image_url}
                          alt="생성 화보"
                          className="h-full w-full object-cover"
                        />
                      )}
                    </div>
                    <figcaption className="text-center text-[11px] text-zinc-500">
                      생성 화보
                    </figcaption>
                  </figure>
                </div>

                {/* 재생성 이력 */}
                {picked.history.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-zinc-400">재생성 이력</p>
                    <div className="flex gap-2 overflow-x-auto">
                      {picked.history.map((h, i) => (
                        <div key={h.image_url} className="shrink-0">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={h.image_url}
                            alt={`${i + 1}차`}
                            className="h-24 w-18 rounded border border-[#2a2a31] object-cover"
                          />
                          <p className="mt-0.5 text-center text-[10px] text-zinc-500">
                            {i + 1}차 · {h.ssim ?? "—"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 프롬프트 수정 */}
                <div>
                  <p className="mb-1 text-xs font-medium text-zinc-400">
                    프롬프트 (재생성 시 반영)
                  </p>
                  <textarea
                    value={editPrompt}
                    onChange={(e) => setEditPrompt(e.target.value)}
                    rows={4}
                    className="w-full rounded-lg border border-[#33333c] bg-[#1b1b1f] px-3 py-2 text-xs text-zinc-200 focus:border-violet-500 focus:outline-none"
                  />
                </div>

                {/* 판정 */}
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    disabled={busyAction}
                    onClick={() => decide(picked, "approve")}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-40"
                  >
                    승인
                  </button>
                  <button
                    type="button"
                    disabled={busyAction}
                    onClick={() => regenerate(picked)}
                    className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-40"
                  >
                    {busyAction ? "처리 중..." : "재생성 (크레딧 소모)"}
                  </button>
                  <button
                    type="button"
                    disabled={busyAction}
                    onClick={() => decide(picked, "discard")}
                    className="rounded-lg border border-red-500/40 px-4 py-2 text-sm font-semibold text-red-300 hover:bg-red-500/10 disabled:opacity-40"
                  >
                    폐기
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

        {view === "library" && (
          <section className="flex flex-col gap-4">
            <header>
              <h1 className="text-2xl font-bold tracking-tight text-zinc-50">
                콘텐츠 라이브러리
              </h1>
              <p className="mt-1 text-sm text-zinc-400">
                생성한 콘텐츠를 카테고리별로 모아보고 화보·릴스를 다시 확인합니다.
              </p>
            </header>

            {/* 카테고리 탭 */}
            <div className="flex flex-wrap gap-1.5">
              {["", ...CATEGORIES.map(([label]) => label)].map((t) => (
                <button
                  key={t || "all"}
                  type="button"
                  onClick={() => setLibCategory(t)}
                  className={`rounded-full border px-3.5 py-1 text-xs transition-colors ${
                    libCategory === t ? CHIP_ON : CHIP_OFF
                  }`}
                >
                  {t || "전체"}
                </button>
              ))}
            </div>

            {libLoading ? (
              <p className="py-10 text-center text-sm text-zinc-500">불러오는 중...</p>
            ) : library.length === 0 ? (
              <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-[#2a2a31] py-14 text-center">
                <p className="text-sm text-zinc-400">아직 생성된 콘텐츠가 없습니다.</p>
                <button
                  type="button"
                  onClick={() => setView("create")}
                  className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-500"
                >
                  생성하러 가기
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {library.map((it) => (
                  <button
                    key={it.product_id}
                    type="button"
                    onClick={() => setSelected(it)}
                    className="group flex flex-col overflow-hidden rounded-xl border border-[#2a2a31] bg-[#141417] text-left transition-colors hover:border-violet-500/50"
                  >
                    <div className="flex aspect-[3/4] items-center justify-center overflow-hidden bg-[#17171b]">
                      {it.image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={it.image_url}
                          alt={it.name ?? "화보"}
                          className="h-full w-full object-cover transition-transform group-hover:scale-105"
                        />
                      ) : (
                        <span className="text-xs text-zinc-600">이미지 없음</span>
                      )}
                    </div>
                    <div className="flex flex-col gap-1 p-2.5">
                      <span className="truncate text-xs font-medium text-zinc-100">
                        {it.name || "이름 없음"}
                      </span>
                      <div className="flex items-center gap-1 text-[10px]">
                        {it.category && (
                          <span className="rounded bg-[#232329] px-1.5 py-0.5 text-zinc-400">
                            {it.category}
                          </span>
                        )}
                        {it.video_url && (
                          <span className="rounded bg-violet-500/15 px-1.5 py-0.5 text-violet-300">
                            릴스
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>
        )}

        {/* 라이브러리 상세 (화보/릴스/SNS) */}
        {selected && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
            onClick={() => setSelected(null)}
          >
            <div
              className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-2xl border border-[#2a2a31] bg-[#141417] p-5"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="mb-3 flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-base font-semibold text-zinc-100">
                    {selected.name || "콘텐츠"}
                  </h3>
                  {selected.category && (
                    <span className="text-xs text-zinc-500">{selected.category}</span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="rounded-md px-2 py-1 text-sm text-zinc-400 hover:text-zinc-100"
                >
                  ✕
                </button>
              </div>

              {selected.image_url && (
                <div className="mb-3">
                  <p className="mb-1 text-xs font-medium text-zinc-400">화보 이미지</p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={selected.image_url}
                    alt="화보"
                    className="w-full rounded-lg border border-[#2a2a31]"
                  />
                </div>
              )}

              {selected.video_url && (
                <div className="mb-3">
                  <p className="mb-1 text-xs font-medium text-zinc-400">릴스 영상</p>
                  <video
                    src={selected.video_url}
                    controls
                    className="w-full rounded-lg border border-[#2a2a31]"
                  />
                </div>
              )}

              {selected.caption && (
                <div className="border-t border-[#2a2a31] pt-3">
                  <p className="mb-1 text-xs font-medium text-zinc-400">SNS 카피</p>
                  <p className="text-sm text-zinc-200">{selected.caption}</p>
                  {selected.hashtags?.length > 0 && (
                    <p className="mt-1 text-sm text-violet-300">
                      {selected.hashtags.join(" ")}
                    </p>
                  )}
                  {selected.ad_copy && (
                    <p className="mt-1 text-sm font-medium text-zinc-100">
                      {selected.ad_copy}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
