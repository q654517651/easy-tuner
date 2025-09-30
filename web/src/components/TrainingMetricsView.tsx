import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { Card, CardBody, CardHeader } from "@heroui/react";
import UplotReact from "uplot-react";
import "uplot/dist/uPlot.min.css";
import { trainingApi } from "../services/api";
import { useTrainingWebSocket } from "../hooks/useTrainingWebSocket";

type Point = { step: number; value: number; wall_time: number };
type Metrics = { loss?: Point[]; learning_rate?: Point[]; epoch?: Point[] };
type SeriesData = { x: number[]; y: number[]; yAvg?: number[] };

// 刷新节流（避免高频重绘）：每 1.5s flush 一次增量
const FLUSH_INTERVAL_MS = 1500;
// 数据上限，避免内存与绘制压力过大
const MAX_POINTS = 5000;

// 工具：简单移动平均（SMA）
function sma(arr: number[], window: number): number[] {
  if (arr.length === 0) return [];
  if (window <= 1 || arr.length <= 3) return arr.slice(); // 数据点太少时直接返回原数组

  const out = new Array(arr.length);
  let sum = 0;

  for (let i = 0; i < arr.length; i++) {
    sum += arr[i];
    if (i >= window) {
      sum -= arr[i - window];
    }

    // 计算当前可用的窗口大小
    const currentWindow = Math.min(i + 1, window);
    out[i] = sum / currentWindow;
  }
  return out;
}

function toSeries(points: Point[], avgWindow = 101): SeriesData {
  const x = points.map(p => p.step);
  const y = points.map(p => p.value);
  const yAvg = sma(y, Math.min(avgWindow, Math.max(3, Math.floor(points.length / 30))));
  return { x, y, yAvg };
}

interface TrainingMetricsViewProps {
  taskId: string;
  avgWindow?: number;
  height?: number;
}

export const TrainingMetricsView: React.FC<TrainingMetricsViewProps> = ({
  taskId,
  avgWindow = 101,
  height = 280
}) => {
  const [metrics, setMetrics] = useState<Metrics>({});
  const [loading, setLoading] = useState(false);
  const [taskState, setTaskState] = useState<string | undefined>(undefined);
  const [containerSize, setContainerSize] = useState({ width: 400, height: 280 });
  const resizeObserverRef = useRef<ResizeObserver>();
  const containerRef = useRef<HTMLDivElement>(null);
  // 待刷新的增量缓冲（不可见于 UI，定时合并到 state）
  const pendingRef = useRef<{ loss: Point[]; lr: Point[]; epoch: Point[] }>({ loss: [], lr: [], epoch: [] });
  const flushTimerRef = useRef<number | null>(null);

  const isRunning = taskState === 'running';

  // 容器尺寸变化处理
  const updateContainerSize = useCallback(() => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      // 每个曲线占用一半宽度，减去gap和Card padding
      const containerBottomPadding = 16; // pb-4 = 16px
      const gapWidth = 24; // gap-6 = 24px
      const availableWidth = rect.width - gapWidth; // 只有gap，没有左右padding
      const halfWidth = availableWidth / 2;
      const cardWidth = Math.max(300, halfWidth - 32); // 减去Card内边距
      const cardHeight = Math.max(200, rect.height - containerBottomPadding - 120); // 减去底部padding、Card头部和底部文字空间
      setContainerSize({ width: cardWidth, height: cardHeight });
    }
  }, []);

  // 设置ResizeObserver监听容器尺寸变化
  useEffect(() => {
    if (containerRef.current) {
      resizeObserverRef.current = new ResizeObserver(() => {
        updateContainerSize();
      });
      resizeObserverRef.current.observe(containerRef.current);
      // 初始化尺寸
      updateContainerSize();
    }

    return () => {
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }
    };
  }, [updateContainerSize]);

  const loadMetrics = async () => {
    try {
      setLoading(true);
      const data = await trainingApi.getTrainingMetrics(taskId);
      setMetrics(data || {});
    } catch (error) {
      console.error('加载训练指标失败:', error);
      setMetrics({});
    } finally {
      setLoading(false);
    }
  };

  // 首次与可见性变化：获取任务状态，决定WS或HTTP
  useEffect(() => {
    const checkStateAndLoad = async () => {
      try {
        const task = await trainingApi.getTask(taskId);
        const state = task?.state || task?.status;
        setTaskState(state);
        if (state !== 'running') {
          await loadMetrics(); // 非训练态，仅HTTP加载一次
        } else {
          setLoading(true); // 训练态等待WS历史返回
        }
      } catch (e) {
        console.error('获取任务状态失败:', e);
        // 回退一次HTTP加载，避免空白
        await loadMetrics();
      }
    };

    checkStateAndLoad();

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        checkStateAndLoad();
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [taskId]);

  // WebSocket: 仅在训练中连接；处理历史与增量指标
  const handleWsMessage = useCallback((message: any) => {
    if (!message || !message.type) return;

    // 状态同步（确保运行态/终态切换及时反映到本地）
    if (message.type === 'state') {
      const s = message.payload?.to_state || message.payload?.current_state;
      if (s) setTaskState(s);
      return;
    }

    // 历史指标（来自TB解析）
    if (message.type === 'historical_metrics') {
      const m = message.payload?.metrics || {};
      setMetrics(m);
      setLoading(false);
      return;
    }

    // 增量指标（training.progress 作为 metric 推送）
    if (message.type === 'metric') {
      const p = message.payload || {};
      const step = typeof p.step === 'number' ? p.step : undefined;
      // 收到增量即解锁 loading
      setLoading(false);
      if (step === undefined) return;

      const now = Date.now() / 1000;
      // 仅在缓冲中合并，按 step 覆盖同步
      if (typeof p.loss === 'number') {
        const arr = pendingRef.current.loss;
        if (arr.length > 0 && arr[arr.length - 1].step === step) {
          arr[arr.length - 1] = { step, value: p.loss, wall_time: arr[arr.length - 1].wall_time ?? now };
        } else {
          arr.push({ step, value: p.loss, wall_time: now });
        }
      }
      if (typeof p.lr === 'number') {
        const arr = pendingRef.current.lr;
        if (arr.length > 0 && arr[arr.length - 1].step === step) {
          arr[arr.length - 1] = { step, value: p.lr, wall_time: arr[arr.length - 1].wall_time ?? now } as any;
        } else {
          arr.push({ step, value: p.lr, wall_time: now } as any);
        }
      }
      if (typeof p.epoch === 'number') {
        const arr = pendingRef.current.epoch;
        if (arr.length > 0 && arr[arr.length - 1].step === step) {
          arr[arr.length - 1] = { step, value: p.epoch, wall_time: arr[arr.length - 1].wall_time ?? now } as any;
        } else {
          arr.push({ step, value: p.epoch, wall_time: now } as any);
        }
      }
      return;
    }

    // 服务端报错时也不要卡在 loading
    if (message.type === 'error') {
      setLoading(false);
      return;
    }
  }, []);

  // 定时将缓冲增量 flush 到 state（不可变追加 + 上限裁剪）
  const flushPending = useCallback(() => {
    const pendLoss = pendingRef.current.loss;
    const pendLr = pendingRef.current.lr;
    const pendEpoch = pendingRef.current.epoch;

    if (pendLoss.length === 0 && pendLr.length === 0 && pendEpoch.length === 0) return;

    setMetrics(prev => {
      const next: Metrics = { ...prev };

      // 合并辅助：同 step 合并（覆盖最后一条）
      const mergeSeries = (prevArr: Point[] | undefined, incArr: Point[]): Point[] => {
        const base = prevArr ? [...prevArr] : [];
        if (incArr.length === 0) return base;
        // 如果最后一个 step 与增量第一个 step 相同，覆盖
        if (base.length > 0 && incArr.length > 0 && base[base.length - 1].step === incArr[0].step) {
          base[base.length - 1] = incArr[0];
          incArr = incArr.slice(1);
        }
        const merged = base.concat(incArr);
        // 上限裁剪
        return merged.length > MAX_POINTS ? merged.slice(merged.length - MAX_POINTS) : merged;
      };

      if (pendLoss.length > 0) {
        next.loss = mergeSeries(prev.loss, pendLoss);
      }
      if (pendLr.length > 0) {
        next.learning_rate = mergeSeries(prev.learning_rate, pendLr);
      }
      if (pendEpoch.length > 0) {
        next.epoch = mergeSeries(prev.epoch, pendEpoch);
      }

      return next;
    });

    // 清空缓冲
    pendingRef.current.loss = [];
    pendingRef.current.lr = [];
    pendingRef.current.epoch = [];
  }, []);

  // 启动/重置 flush 定时器
  useEffect(() => {
    if (flushTimerRef.current) {
      clearInterval(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    flushTimerRef.current = window.setInterval(flushPending, FLUSH_INTERVAL_MS);
    return () => {
      if (flushTimerRef.current) {
        clearInterval(flushTimerRef.current);
        flushTimerRef.current = null;
      }
      // 卸载时清空缓冲，避免跨任务污染
      pendingRef.current.loss = [];
      pendingRef.current.lr = [];
      pendingRef.current.epoch = [];
    };
  }, [taskId, flushPending]);

  const handleWsFinal = useCallback((status: string) => {
    // 终态：断开WS，回退一次HTTP拉取最终指标
    setTaskState(status);
    loadMetrics();
  }, [loadMetrics]);

  useTrainingWebSocket({
    taskId,
    isRunning,
    taskState,
    tab: 'metrics',
    onMessage: handleWsMessage,
    onFinal: handleWsFinal,
  });

  // 初始加载（移除单独的加载逻辑，已合并到轮询逻辑中）

  // 处理数据转换
  const lossSeries = useMemo(() => {
    if (!metrics.loss || metrics.loss.length === 0) return { x: [], y: [], yAvg: [] };
    return toSeries(metrics.loss, avgWindow);
  }, [metrics.loss, avgWindow]);

  const lrSeries = useMemo(() => {
    if (!metrics.learning_rate || metrics.learning_rate.length === 0) return { x: [], y: [], yAvg: [] };

    // 静默：不打印学习率范围

    return toSeries(metrics.learning_rate, Math.max(21, Math.floor(avgWindow / 4)));
  }, [metrics.learning_rate, avgWindow]);

  // uPlot 数据格式： [x, y1, y2, ...]
  const lossData = useMemo(() => {
    if (!lossSeries.x || lossSeries.x.length === 0) return [[], [], []];
    return [lossSeries.x, lossSeries.y, lossSeries.yAvg ?? []];
  }, [lossSeries]);

  const lrData = useMemo(() => {
    if (!lrSeries.x || lrSeries.x.length === 0) return [[], [], []];
    return [lrSeries.x, lrSeries.y, lrSeries.yAvg ?? []];
  }, [lrSeries]);

  // uPlot配置 - 使用containerSize
  const createUplotOptions = useMemo(() => (title: string, yLabel: string, isLearningRate: boolean = false): uPlot.Options => ({
    title,
    width: containerSize.width,
    height: containerSize.height,
    pxAlign: 0, // 抗锯齿
    cursor: {
      show: true,
      x: true,
      y: true,
      drag: {
        x: true,
        y: false,
      },
    },
    legend: {
      show: true,
    },
    scales: {
      x: {
        time: false,
      },
      y: {
        auto: true,
        range: isLearningRate ? [0, null] : [null, null], // 学习率从0开始
      },
    },
    axes: [
      {
        grid: { show: true },
        stroke: "#9aa0a6",
        ticks: { show: true },
      },
      {
        label: "", // 移除y轴标签文案
        stroke: "#9aa0a6",
        ticks: { show: true },
        grid: { show: true },
        values: isLearningRate
          ? (u: any, vals: number[]) => vals.map(v => v.toExponential(2))
          : (u: any, vals: number[]) => vals.map(v => v.toFixed(6)),
      },
    ],
    series: [
      {}, // x 轴占位
      {
        label: "实际值",
        stroke: isLearningRate ? "#10b981" : "#3b82f6",
        width: 3,
        spanGaps: true,
        points: { show: false },
        value: isLearningRate
          ? (u: any, v: number) => v?.toExponential(3) || "0"
          : (u: any, v: number) => v?.toFixed(6) || "0",
      },
      {
        label: "平均值",
        stroke: isLearningRate ? "#22c55e" : "#60a5fa",
        width: 4,
        dash: [8, 6],
        spanGaps: true,
        points: { show: false },
        value: isLearningRate
          ? (u: any, v: number) => v?.toExponential(3) || "0"
          : (u: any, v: number) => v?.toFixed(6) || "0",
      },
    ],
  }), [containerSize]);

  const EmptyState = ({ title }: { title: string }) => (
    <div className="flex flex-col items-center justify-center py-8 text-default-500">
      <div className="text-4xl mb-2">📊</div>
      <div className="text-sm">暂无{title}数据</div>
      <div className="text-xs text-default-400 mt-1">训练过程中会自动生成</div>
    </div>
  );

  const LoadingState = () => (
    <div className="flex items-center justify-center py-8">
      <div className="text-default-500">加载中...</div>
    </div>
  );

  return (
    <div className="grid grid-cols-2 gap-6 h-full pb-4" ref={containerRef}>
      {/* Loss曲线 */}
      <Card className="h-full flex flex-col bg-[#F9F9FA] dark:bg-white/4 shadow-none">
        <CardHeader className="pb-2 px-4 pt-4">
          <h3 className="text-lg font-semibold">Loss曲线</h3>
        </CardHeader>
        <CardBody className="flex-1 px-4 pb-6 pt-0 overflow-visible">
          {loading ? (
            <LoadingState />
          ) : (metrics.loss && metrics.loss.length > 0 && lossData[0].length > 0) ? (
            <div className="w-full h-full">
              <UplotReact
                options={createUplotOptions("", "Loss", false)}
                data={lossData}
              />
            </div>
          ) : (
            <EmptyState title="Loss" />
          )}
        </CardBody>
      </Card>

      {/* 学习率曲线 */}
      <Card className="h-full flex flex-col bg-[#F9F9FA] dark:bg-white/4 shadow-none">
        <CardHeader className="pb-2 px-4 pt-4">
          <h3 className="text-lg font-semibold">学习率曲线</h3>
        </CardHeader>
        <CardBody className="flex-1 px-4 pb-6 pt-0 overflow-visible">
          {loading ? (
            <LoadingState />
          ) : (metrics.learning_rate && metrics.learning_rate.length > 0 && lrData[0].length > 0) ? (
            <div className="w-full h-full">
              <UplotReact
                options={createUplotOptions("", "Learning Rate", true)}
                data={lrData}
              />
            </div>
          ) : (
            <EmptyState title="学习率" />
          )}
        </CardBody>
      </Card>
    </div>
  );
};

// 导出默认组件以保持向后兼容
export default TrainingMetricsView;
