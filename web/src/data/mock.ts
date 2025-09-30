// src/data/mock.ts

/** 列表页用到的数据集摘要 */
export type DatasetBrief = {
  id: string;
  name: string;
  kind: "图片" | "视频" | "控制图";
  total: number;
  labeled: number;
};

export const datasets: DatasetBrief[] = Array.from({ length: 4 }).map((_, i) => ({
  id: String(i + 1),
  name: `Image Dataset_2025+0813`,
  kind: "图片",
  total: 50,
  labeled: 50,
}));

/** 详情页用到的媒体条目（多比例测试） */
export type MediaItem = {
  id: string;
  filename: string;
  url: string;
  caption: string;
};

const CAPTION =
  "A dreamy and luxurious 3D fantasy art style, a beautifully illuminated scene showcases a large, ornate treasure chest filled with glowing gold and gems.";

// 横图（16:9）+ 竖图（3:4）+ 方图（1:1）
export const sampleItems: MediaItem[] = [
  ...Array.from({ length: 6 }).map((_, i) => ({
    id: `w_${i + 1}`,
    filename: `${i + 1}.png`,
    url: `https://picsum.photos/seed/wide-${i}/1280/720`,
    caption: CAPTION,
  })),
  ...Array.from({ length: 6 }).map((_, i) => ({
    id: `p_${i + 1}`,
    filename: `${i + 7}.png`,
    url: `https://picsum.photos/seed/portrait-${i}/900/1200`,
    caption: CAPTION,
  })),
  ...Array.from({ length: 6 }).map((_, i) => ({
    id: `s_${i + 1}`,
    filename: `${i + 13}.png`,
    url: `https://picsum.photos/seed/square-${i}/1000/1000`,
    caption: CAPTION,
  })),
];
