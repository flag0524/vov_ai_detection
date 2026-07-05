// 상품 업로드 → AI 생성 파이프라인 실행 → 화보/영상/SNS 카피 결과 확인 화면
"use client";

import { useState } from "react";

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
  video_url: string;
  sns: {
    caption: string;
    hashtags: string[];
    ad_copy: string;
  };
  stubs: { image: boolean; video: boolean };
};

type Stage = "idle" | "uploading" | "generating" | "done" | "error";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);

  async function handleGenerate() {
    if (!file) return;
    setError(null);
    setResult(null);

    try {
      setStage("uploading");
      const form = new FormData();
      form.append("file", file);
      const uploadRes = await fetch(`${API_BASE}/product/upload`, {
        method: "POST",
        body: form,
      });
      if (!uploadRes.ok) throw new Error(`업로드 실패 (${uploadRes.status})`);
      const { product_id } = await uploadRes.json();

      setStage("generating");
      const pipelineRes = await fetch(`${API_BASE}/pipeline/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id }),
      });
      if (!pipelineRes.ok) throw new Error(`생성 실패 (${pipelineRes.status})`);
      const data: PipelineResult = await pipelineRes.json();

      setResult(data);
      setStage("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStage("error");
    }
  }

  return (
    <div className="flex flex-col flex-1 items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex flex-1 w-full max-w-2xl flex-col gap-8 py-16 px-6">
        <header>
          <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">
            JBLANC AI Fashion 생성
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            상품 이미지를 업로드하면 화보 이미지·릴스 영상·SNS 카피를 자동 생성합니다.
          </p>
        </header>

        <section className="flex flex-col gap-3 rounded-lg border border-zinc-200 p-5 dark:border-zinc-800">
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
          <button
            onClick={handleGenerate}
            disabled={!file || stage === "uploading" || stage === "generating"}
            className="rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background disabled:opacity-40"
          >
            {stage === "uploading" && "업로드 중..."}
            {stage === "generating" && "생성 중..."}
            {(stage === "idle" || stage === "done" || stage === "error") && "생성 시작"}
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </section>

        {result && (
          <section className="flex flex-col gap-6">
            {(result.stubs.image || result.stubs.video) && (
              <p className="rounded-md bg-amber-100 px-3 py-2 text-xs text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                ⚠ 스텁 결과물 포함 — 외부 생성 API 미호출 (자격증명/크레딧 확인 필요)
              </p>
            )}

            <div>
              <h2 className="text-lg font-medium">화보 이미지</h2>
              <p className="mt-1 break-all text-sm text-zinc-500">{result.image_url}</p>
              <p className="mt-2 text-sm">
                상품 원본 유지율(SSIM): {result.quality.ssim_score} —{" "}
                {result.quality.overall_pass ? "통과" : "재생성 필요"}
              </p>
            </div>

            <div>
              <h2 className="text-lg font-medium">릴스 영상</h2>
              <p className="mt-1 break-all text-sm text-zinc-500">{result.video_url}</p>
            </div>

            <div>
              <h2 className="text-lg font-medium">SNS 카피</h2>
              <p className="mt-1 text-sm">{result.sns.caption}</p>
              <p className="mt-1 text-sm text-zinc-500">
                {result.sns.hashtags.join(" ")}
              </p>
              <p className="mt-1 text-sm font-medium">{result.sns.ad_copy}</p>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
