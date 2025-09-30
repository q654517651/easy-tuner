// src/data/settings.ts
export type ReleaseItem = {
  id: string;
  tag: string;     // #3.214
  dataset: string; // Dataset2141213
  date?: string;
};

export const releases: ReleaseItem[] = Array.from({ length: 5 }).map((_, i) => ({
  id: `r_${i + 1}`,
  tag: "#3.214",
  dataset: "Dataset2141213",
  date: "2025-08-16",
}));

export type ModelPathItem = {
  id: string;
  title: string; // Qwen-Image / Wan / Flux-kontext
  dit?: string;
  vae?: string;
  textEncoder?: string;
};

export const modelPaths: ModelPathItem[] = [
  { id: "qwen", title: "Qwen-Image", dit: "Qwen-image", vae: "", textEncoder: "Master" },
  { id: "wan", title: "Wan", dit: "Qwen-image", vae: "", textEncoder: "Master" },
  { id: "flux", title: "Flux–kontext", dit: "Qwen-image", vae: "", textEncoder: "Master" },
];

export type LabelingSetting = {
  model: string;        // 选择打标模型
  latency: number;      // 调用延迟
  prompt: string;       // 打标 prompt
  apiKey: string;
  apiBase: string;
  picker: string;       // gpt-4o mini / gpt-5 mini ...
};

export const labelingDefault: LabelingSetting = {
  model: "Qwen vl 2.5b",
  latency: 1,
  prompt: "test",
  apiKey: "as,jdjhlkashjdlkasjdjkk",
  apiBase: "asdsajdladsjk",
  picker: "GPT-5 mini",
};
