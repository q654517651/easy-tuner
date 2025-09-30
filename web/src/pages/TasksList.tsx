import React, { useEffect, useState } from "react";
import { Skeleton, Button } from "@heroui/react";
import { Link } from "react-router-dom";
import HeaderBar from "../ui/HeaderBar";
import TaskRow from "../ui/TaskRow";
import { trainingApi } from "../services/api";
import EmptyState from "../ui/EmptyState";
import EmptyImg from "../assets/img/EmptyDataset.png?inline";

// 导入统一的任务类型
import type { TrainTask } from "../data/tasks";

// 页面级缓存
let _tasksCache: TrainTask[] | null = null;

export default function TasksList() {
  const [tasks, setTasks] = useState<TrainTask[]>(_tasksCache ?? []);
  const [loading, setLoading] = useState(_tasksCache === null); // 首次无缓存才显示加载
  const [error, setError] = useState<string | null>(null);

  // 加载训练任务列表
  const loadTasks = async (opts?: { silent?: boolean }) => {
    try {
      if (!opts?.silent) setLoading(true);
      setError(null);
      const taskList = await trainingApi.listTasks();

      // 转换API数据为UI组件需要的格式
      const convertedTasks: TrainTask[] = taskList.map((task: any) => ({
        id: task.id,
        name: task.name,
        status: mapTrainingStateToStatus(task.state),
        model: task.training_type || "Unknown",
        createdAt: formatDate(task.created_at),
        // 列表进度改为“步数/总步数”
        total: task.total_steps || 0,
        done: task.current_step || 0,
        throughput: task.speed || 0,
        eta: formatEta(task.eta_seconds)
      }));

      _tasksCache = convertedTasks; // 写入缓存
      setTasks(convertedTasks);
    } catch (err: any) {
      console.error('加载训练任务失败:', err);
      setError(err.message || '加载训练任务失败');
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
  }, []);

  // 当存在运行中任务时，轻量轮询（3s）作为 WS 并发上限的兜底
  useEffect(() => {
    const hasRunning = tasks.some(t => t.status === 'running');
    if (!hasRunning) return;
    if (document.visibilityState !== 'visible') return;
    let timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        loadTasks({ silent: true });
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [tasks]);

  // 映射后端状态到前端状态
  const mapTrainingStateToStatus = (state: string): TrainTask['status'] => {
    // 直接返回后端状态，确保前后端状态完全一致
    switch (state) {
      case 'pending': return 'pending';
      case 'running': return 'running';
      case 'completed': return 'completed';
      case 'failed': return 'failed';
      case 'cancelled': return 'cancelled';
      default: return 'pending'; // 默认状态
    }
  };

  // 格式化日期
  const formatDate = (dateString: string): string => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      return date.toISOString().split('T')[0]; // YYYY-MM-DD格式
    } catch {
      return dateString;
    }
  };

  // 格式化ETA
  const formatEta = (etaSeconds: number | null | undefined): string => {
    if (!etaSeconds || etaSeconds <= 0) return '';

    const hours = Math.floor(etaSeconds / 3600);
    const minutes = Math.floor((etaSeconds % 3600) / 60);

    if (hours > 0) {
      return `${hours}h ${minutes}min`;
    } else {
      return `${minutes}min`;
    }
  };

  // 延迟展示骨架，避免极短加载时的闪烁
  const [showLoading, setShowLoading] = useState(false);
  useEffect(() => {
    if (!loading) { setShowLoading(false); return; }
    const t = window.setTimeout(() => setShowLoading(true), 150);
    return () => window.clearTimeout(t);
  }, [loading]);

  // 计算UI状态
  const isSkeleton = loading && showLoading;      // 还在加载，且超过了骨架延迟门槛
  const isEmpty = !loading && tasks.length === 0; // 加载完成，且数据为空
  const hasData = tasks.length > 0;               // 有数据

  if (error) {
    return (
      <div className="flex flex-col h-full">
        <HeaderBar
          crumbs={[{ label: "任务列表" }]}
          actions={
            <Button
              as={Link as any}
              to="/train/create"
              variant="bordered"
              size="sm"
              startContent="➕"
            >
              创建训练任务
            </Button>
          }
        />
        <div className="p-6 flex items-center justify-center">
          <div className="text-red-600">加载失败: {error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <HeaderBar
        crumbs={[{ label: "任务列表" }]}
        actions={
          <Button
            as={Link as any}
            to="/train/create"
            variant="bordered"
            size="sm"
            startContent="➕"
          >
            创建训练任务
          </Button>
        }
      />

      <div className="p-6 space-y-4 flex-1 min-h-0 relative">
        {/* 骨架屏层 - 条件渲染 */}
        {isSkeleton && (
          <div className="space-y-3">
            {[0,1,2].map(i => (
              <div key={i} className="rounded-2xl bg-content1 ring-1 ring-black/5 dark:ring-white/10 p-4">
                <div className="flex items-center gap-3">
                  <Skeleton className="w-12 h-12 rounded-xl">
                    <div className="w-12 h-12 bg-default-300" />
                  </Skeleton>
                  <div className="flex-1 min-w-0 space-y-2">
                    <Skeleton className="h-4 w-48 rounded-lg">
                      <div className="h-4 w-48 bg-default-200" />
                    </Skeleton>
                    <Skeleton className="h-3 w-72 rounded-lg">
                      <div className="h-3 w-72 bg-default-200" />
                    </Skeleton>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 空态层 - 只在非加载且确实为空时显示 */}
        {isEmpty && (
          <EmptyState image={EmptyImg} message="暂无训练任务" />
        )}

        {/* 数据列表层 - 有数据就显示 */}
        {hasData && (
          <div className={`space-y-4 transition-opacity duration-300 ${loading ? 'opacity-70' : 'opacity-100'}`}>
            {tasks.map((task) => (
              <TaskRow key={task.id} task={task} onTaskDeleted={loadTasks} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
