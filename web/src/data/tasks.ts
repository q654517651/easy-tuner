export type TrainTask = {
  id: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  model: "Qwen-image" | "Flux" | "Stable";
  createdAt: string; // YYYY-MM-DD
  total: number;
  done: number;
  throughput: number; // 速度值
  throughputUnit?: string; // 速度单位：'it/s' 或 's/it'
  eta: string; // 10h 30min
};

export const tasks: TrainTask[] = [
  {
    id: "t_1",
    name: "Dataset_2025+0813",
    status: "running",
    model: "Qwen-image",
    createdAt: "2025-08-16",
    total: 3000,
    done: 1920,
    throughput: 1.92,
    eta: "10h 30min",
  },
  {
    id: "t_2",
    name: "Dataset_2025+0813",
    status: "running",
    model: "Qwen-image",
    createdAt: "2025-08-16",
    total: 3000,
    done: 1875,
    throughput: 1.92,
    eta: "10h 30min",
  },
  {
    id: "t_3",
    name: "Dataset_2025+0813",
    status: "running",
    model: "Qwen-image",
    createdAt: "2025-08-16",
    total: 3000,
    done: 1710,
    throughput: 1.92,
    eta: "10h 30min",
  },
  {
    id: "t_4",
    name: "Dataset_2025+0813",
    status: "running",
    model: "Qwen-image",
    createdAt: "2025-08-16",
    total: 3000,
    done: 1600,
    throughput: 1.92,
    eta: "10h 30min",
  },
];
