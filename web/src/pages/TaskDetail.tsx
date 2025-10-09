import { useParams, useNavigate } from "react-router-dom";
import { useState, useEffect, useRef, useCallback } from "react";
import { Tabs, Tab } from "@heroui/react";
import HeaderBar from "../ui/HeaderBar";
import { Button, Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, useDisclosure, addToast } from "@heroui/react";
import { trainingApi, systemApi, type GPUMetrics } from "../services/api";
import { TaskSamplesView } from "../components/TaskSamplesView";
import { TrainingMetricsView } from "../components/TrainingMetricsView";
import { useGpuMetricsWS } from "../hooks/useGpuMetricsWS";
import { useTrainingWebSocket } from "../hooks/useTrainingWebSocket";
import RuntimeInstallModal from "../components/RuntimeInstallModal";
import PowerIcon from "../assets/traing_icon/power.svg";
import VramIcon from "../assets/traing_icon/vram.svg";
import TemperatureIcon from "../assets/traing_icon/temperature.svg";
import SpeedIcon from "../assets/traing_icon/speed.svg";
import CountdownIcon from "../assets/traing_icon/countdown.svg";

function StatCard({ iconPath, label, value }: { iconPath: string; label: string; value: string | number }) {
  return (
    <div className="flex items-center gap-2 flex-1">
      <img src={iconPath} alt={label} className="w-10 h-10" />
      <div className="flex flex-col">
        <div className="text-sm opacity-60">{label}</div>
        <div className="font-bold">{value}</div>
      </div>
    </div>
  );
}


export default function TaskDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [selectedTab, setSelectedTab] = useState("progress");
  const [task, setTask] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const logContainerRef = useRef<HTMLDivElement | null>(null);
  const [autoFollow, setAutoFollow] = useState(true);
  const logOffsetRef = useRef(0);
  const [samplesRefreshTick, setSamplesRefreshTick] = useState(0);
  // 顶部操作：取消/重启 弹窗与状态
  const { isOpen: isCancelOpen, onOpen: onCancelOpen, onClose: onCancelClose } = useDisclosure();
  const { isOpen: isRestartOpen, onOpen: onRestartOpen, onClose: onRestartClose } = useDisclosure();
  const [actionHover, setActionHover] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [showRuntimeModal, setShowRuntimeModal] = useState(false);

  // GPU指标状态
  const [gpuMetrics, setGpuMetrics] = useState<GPUMetrics[]>([]);

  // WebSocket消息处理回调
  const handleWebSocketMessage = useCallback((message: any) => {

    if (message.type === 'log_batch') {
      const newLines: string[] = message.lines || [];
      if (newLines.length > 0) {
        setLogs(prev => [...prev, ...newLines]);
      }
      const batchNew = (message.newOffset ?? message.new_offset);
      if (typeof batchNew === 'number') {
        logOffsetRef.current = batchNew;
      } else {
        logOffsetRef.current = (logOffsetRef.current || 0) + (newLines.length || 0);
      }
    } else if (message.type === 'historical_logs') {
      const newLines: string[] = message.payload?.logs || message.lines || [];
      if (newLines.length > 0) {
        setLogs(prev => [...prev, ...newLines]);
      }
      const histNew = (message.payload?.newOffset ?? message.payload?.new_offset ?? message.newOffset ?? message.new_offset);
      if (typeof histNew === 'number') {
        logOffsetRef.current = histNew;
      } else {
        logOffsetRef.current = (logOffsetRef.current || 0) + (newLines.length || 0);
      }
    } else if (message.type === 'log') {
      const logMessage = message.payload?.message ?? message.message ?? message.data?.message ?? '';
      if (logMessage) {
        setLogs(prev => [...prev, logMessage]);
        const oneNew = (message.payload?.newOffset ?? message.payload?.new_offset ?? message.newOffset ?? message.new_offset);
        if (typeof oneNew === 'number') {
          logOffsetRef.current = oneNew;
        } else {
          logOffsetRef.current++;
        }
      }
    } else if (message.type?.startsWith('training_task_log_')) {
      const logMessage = message.data?.message || message.data?.log || '';
      if (logMessage) {
        setLogs(prev => [...prev, logMessage]);
        logOffsetRef.current++;
      }
    } else if (message.type === 'training_task_restart' || message.type?.startsWith('training_task_restart_')) {
      setLogs([]);
      logOffsetRef.current = 0;
    } else if (message.type === 'file' || message.type === 'file_changed') {
      setSamplesRefreshTick(t => t + 1);
    } else if (message.type === 'state') {
      const newState = message.payload?.to_state || message.payload?.current_state;
      if (newState && newState !== task?.state) {
        const prevState = task?.state;
        const isRestart = prevState && ['failed', 'cancelled', 'completed'].includes(prevState) && newState === 'running';
        if (isRestart) {
          setLogs([]);
          logOffsetRef.current = 0;
        }
        setTask((prev: any) => prev ? { ...prev, state: newState } : prev);
        console.info(`[TaskDetail] 状态变更: ${prevState ?? 'unknown'} -> ${newState}`);
      }
    } else if (message.type === 'metric') {
      const p = message.payload || {};
      setTask((prev: any) => {
        if (!prev) return prev;
        const next = { ...prev };
        if (typeof p.step === 'number') next.current_step = p.step;
        if (typeof p.total_steps === 'number') next.total_steps = p.total_steps;
        if (typeof p.epoch === 'number') next.current_epoch = p.epoch;
        if (typeof p.lr === 'number') next.learning_rate = p.lr;
        if (typeof p.loss === 'number') next.loss = p.loss;
        if (typeof p.speed === 'number') next.speed = p.speed;
        if (typeof p.eta_seconds === 'number') next.eta_seconds = p.eta_seconds;
        if (typeof p.progress === 'number') next.progress = p.progress;
        return next;
      });
    }
  }, [task?.state]);

  const handleTrainingFinal = useCallback((status: string) => {
    // 更新任务状态 - 修正：使用 state 字段
    if (!status) return;
    setTask((prev: any) => prev ? { ...prev, state: status } : prev);
  }, []);

  // 判断是否为活跃训练状态（需要WebSocket连接）
  const isActiveTraining = task?.state === 'running';

  // 静默：不在每次渲染打印状态

  // ==================== Phase 1 修复：WebSocket 终态重连问题 ====================
  // 使用新的WebSocket Hook（增加 taskState 参数用于终态判断）
  const { connected } = useTrainingWebSocket({
    taskId: id || '',
    isRunning: isActiveTraining, // 修正：preparing 和 running 状态都需要连接
    taskState: task?.state,      // Phase 1 新增：用于终态判断，解决重连问题
    tab: selectedTab,
    sinceOffset: logOffsetRef.current,
    onMessage: handleWebSocketMessage,
    onFinal: handleTrainingFinal,
    enabled: selectedTab !== 'metrics'
  });
  // TODO Phase 2: 移除 isActiveTraining，改为基于统一状态管理器

  // 加载任务详情
  useEffect(() => {
    if (!id) return;

    const loadTask = async () => {
      try {
        setLoading(true);
        const taskDetail = await trainingApi.getTask(id);
        if (!taskDetail) {
          setError("任务不存在");
          return;
        }
        setTask(taskDetail);
        const initialLogs = taskDetail.logs || [];
        setLogs(initialLogs);
        // 初始化日志偏移量
        logOffsetRef.current = initialLogs.length;
      } catch (err: any) {
        console.error('加载任务详情失败:', err);
        setError(err.message || '加载任务详情失败');
      } finally {
        setLoading(false);
      }
    };

    loadTask();
  }, [id]);

  // 获取GPU指标数据（非运行态首屏兜底）
  const fetchGPUMetrics = useCallback(async () => {
    try {
      const response = await systemApi.getGPUMetrics();
      setGpuMetrics(response.data.gpus);
    } catch (error) {
      console.error('获取GPU指标失败:', error);
    }
  }, []);

  // GPU 指标：训练中走 WS；非训练仅加载一次
  useEffect(() => {
    if (selectedTab !== 'progress') return;
    const isTraining = task?.state === 'running';
    if (!isTraining) {
      fetchGPUMetrics();
    }
  }, [selectedTab, task?.state, fetchGPUMetrics]);

  // 训练中：启用 GPU WS（可见且在线）
  useGpuMetricsWS({
    enabled: selectedTab === 'progress' && task?.state === 'running' && document.visibilityState === 'visible' && navigator.onLine,
    onUpdate: (g) => setGpuMetrics(g ?? []),
  });


  // 日志变化时：若当前在底部，则自动滚动到底部；否则保持用户当前位置
  useEffect(() => {
    const el = logContainerRef.current;
    if (!el) return;
    if (!autoFollow) return;
    el.scrollTop = el.scrollHeight;
  }, [logs, autoFollow]);

  // 控制按钮处理
  const handleControl = async (action: 'start' | 'stop') => {
    if (!id) return;

    try {
      if (action === 'start') {
        // 仅在终态→重试时清空终端日志；新任务不打印“重试”文案
        const prevState = task?.state;
        const isRetry = prevState && ['failed', 'cancelled', 'completed'].includes(prevState);
        if (isRetry) {
          setLogs([]);
          logOffsetRef.current = 0;
        }

        await trainingApi.startTask(id);
        // 启动任务后，立即设置临时状态以建立WebSocket连接
        setTask((prev: any) => prev ? { ...prev, state: 'running' } : prev);
      } else {
        await trainingApi.stopTask(id);
      }
      // 延迟重新加载任务详情，让WebSocket有时间接收状态更新
      setTimeout(async () => {
        const updatedTask = await trainingApi.getTask(id);
        setTask(updatedTask);
      }, 1000);
    } catch (error: any) {
      console.error(`${action}任务失败:`, error);

      // 检查是否为 PYTHON_MISSING 错误
      if (error?.detail?.error_code === 'PYTHON_MISSING') {
        setShowRuntimeModal(true);
      } else {
        addToast({
          title: `${action === 'start' ? '启动' : '停止'}任务失败`,
          description: String(error?.detail?.message || error?.message || error),
          color: 'danger',
          timeout: 3000
        });
      }
    }
  };

  const getStatusInfo = (state: string) => {
    switch (state) {
      case 'pending': return { label: '⏳ 等待中', variant: 'outline' as const };
      case 'running': return { label: '▶️ 训练中', variant: 'primary' as const };
      case 'completed': return { label: '✅ 已完成', variant: 'success' as const };
      case 'failed': return { label: '❌ 失败', variant: 'danger' as const };
      case 'cancelled': return { label: '⏹️ 已取消', variant: 'outline' as const };
      default:
        console.warn('未知状态值:', state);
        return { label: '❓ 未知', variant: 'outline' as const };
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <HeaderBar crumbs={[{ label: "任务列表", path: "/tasks" }, { label: "加载中..." }]} />
        <div className="p-6 flex items-center justify-center">
          <div className="text-gray-600">正在加载训练任务详情...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-full">
        <HeaderBar crumbs={[{ label: "任务列表", path: "/tasks" }, { label: "错误" }]} />
        <div className="p-6 flex items-center justify-center">
          <div className="text-red-600">{error}</div>
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="flex flex-col h-full">
        <HeaderBar crumbs={[{ label: "任务列表", path: "/tasks" }, { label: "任务不存在" }]} />
        <div className="p-6 flex items-center justify-center">
          <div className="text-gray-600">任务不存在</div>
        </div>
      </div>
    );
  }

  const statusInfo = getStatusInfo(task.state);
  const canStart = task.state === 'pending';
  const isRunningState = task.state === 'running';
  const isTerminal = ['failed','cancelled','completed'].includes(task.state);

  return (
    <div className="flex flex-col h-full">
      <HeaderBar
        crumbs={[
          { label: "任务列表", path: "/tasks" },
          { label: task.name },
        ]}
        actions={(
          <div className="flex items-center gap-2">
            {canStart && (
              <Button
                color="primary"
                size="sm"
                onPress={() => handleControl('start')}
              >
                <span className="mr-1">▶️</span> 开始
              </Button>
            )}

            {isRunningState && (
              <Button
                color={actionHover ? "danger" : "primary"}
                size="sm"
                onMouseEnter={() => setActionHover(true)}
                onMouseLeave={() => setActionHover(false)}
                onPress={() => onCancelOpen()}
                isDisabled={actionLoading}
              >
                <span className="mr-1">🚫</span> {actionHover ? '取消训练' : '训练中'}
              </Button>
            )}

            {isTerminal && (
              <Button
                variant="bordered"
                color={actionHover ? "warning" : "default"}
                size="sm"
                onMouseEnter={() => setActionHover(true)}
                onMouseLeave={() => setActionHover(false)}
                onPress={() => onRestartOpen()}
                isDisabled={actionLoading}
              >
                {actionHover ? '重新开始' : (
                  task.state === 'cancelled' ? '任务取消' : task.state === 'failed' ? '任务失败' : '已完成'
                )}
              </Button>
            )}

            {/* 取消确认弹窗 */}
            <Modal isOpen={isCancelOpen} onClose={() => { if (!actionLoading) onCancelClose(); }} placement="center">
              <ModalContent>
                <ModalHeader className="flex flex-col gap-1">取消训练</ModalHeader>
                <ModalBody>
                  <p>训练进行中，是否取消？</p>
                </ModalBody>
                <ModalFooter>
                  <Button variant="light" onPress={onCancelClose} isDisabled={actionLoading}>取消</Button>
                  <Button color="danger" isLoading={actionLoading} onPress={async () => {
                    if (!id) return;
                    try {
                      setActionLoading(true);
                      await trainingApi.stopTask(id);
                      onCancelClose();
                      setTask((prev: any) => prev ? { ...prev, state: 'cancelled' } : prev);
                      addToast({ title: '已取消训练', color: 'success', timeout: 2000 });
                    } catch (e) {
                      addToast({ title: '取消失败', description: String(e), color: 'danger', timeout: 2500 });
                    } finally {
                      setActionLoading(false);
                      // 延迟刷新一次详情，确保状态与后端一致
                      setTimeout(async () => { if (id) setTask(await trainingApi.getTask(id)); }, 800);
                    }
                  }}>确认取消</Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* 重启确认弹窗 */}
            <Modal isOpen={isRestartOpen} onClose={() => { if (!actionLoading) onRestartClose(); }} placement="center">
              <ModalContent>
                <ModalHeader className="flex flex-col gap-1">重新开始训练</ModalHeader>
                <ModalBody>
                  <p>重新开始将覆盖之前的记录，是否继续？</p>
                </ModalBody>
                <ModalFooter>
                  <Button variant="light" onPress={onRestartClose} isDisabled={actionLoading}>取消</Button>
                  <Button color="warning" isLoading={actionLoading} onPress={async () => {
                    if (!id) return;
                    try {
                      setActionLoading(true);
                      // 清空前端日志视图与偏移
                      setLogs([]);
                      logOffsetRef.current = 0;
                      await trainingApi.startTask(id);
                      onRestartClose();
                      setTask((prev: any) => prev ? { ...prev, state: 'running' } : prev);
                      addToast({ title: '已重新开始训练', color: 'success', timeout: 2000 });
                    } catch (e) {
                      addToast({ title: '重启失败', description: String(e), color: 'danger', timeout: 2500 });
                    } finally {
                      setActionLoading(false);
                      setTimeout(async () => { if (id) setTask(await trainingApi.getTask(id)); }, 800);
                    }
                  }}>确认重新开始</Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </div>
        )}
      />

      <div className="h-[72px] shrink-0 bg-white/40 dark:bg-black/10 backdrop-blur px-4 flex items-center justify-between">
        <Tabs
          selectedKey={selectedTab}
          onSelectionChange={(key) => setSelectedTab(key as string)}
          variant="solid"
        >
          <Tab key="progress" title="训练进度" />
          <Tab key="metrics" title="训练结果" />
          <Tab key="samples" title="采样结果" />
        </Tabs>
      </div>

      <div className="px-5 pb-5 flex-1 flex flex-col overflow-hidden min-h-0 space-y-6">
        {selectedTab === "progress" && (
          <div className="flex-1 flex flex-col min-h-0 space-y-4">
            {/* 训练进度 */}
            <div className="rounded-3xl bg-neutral-100/60 dark:bg-white/5 p-4 sm:p-5 space-y-4">
              <div className="flex items-center justify-between mb-2">
                <div className="font-medium">训练进度</div>
                <div className="text-sm opacity-60">
                  {task.current_epoch || 0} / {task.total_steps || 0}
                </div>
              </div>
              <div className="h-2 rounded-full bg-neutral-200 overflow-hidden">
                <div
                  className="h-full bg-sky-500"
                  style={{ width: `${(task.progress || 0) * 100}%` }}
                />
              </div>

              {/* 训练统计 */}
              <div className="flex gap-2 pt-2">
                <StatCard
                  iconPath={VramIcon}
                  label="显存占用"
                  value={gpuMetrics[0] ? `${(gpuMetrics[0].memory_used / 1024).toFixed(1)}GB / ${(gpuMetrics[0].memory_total / 1024).toFixed(1)}GB` : 'N/A'}
                />
                <StatCard
                  iconPath={TemperatureIcon}
                  label="GPU温度"
                  value={gpuMetrics[0] ? `${gpuMetrics[0].temperature}°C` : 'N/A'}
                />
                <StatCard
                  iconPath={PowerIcon}
                  label="GPU功耗"
                  value={gpuMetrics[0] ? `${gpuMetrics[0].power_draw}W` : 'N/A'}
                />
                <StatCard
                  iconPath={SpeedIcon}
                  label="训练速度"
                  value={task.speed ? `${task.speed.toFixed(2)} it/s` : 'N/A'}
                />
                <StatCard
                  iconPath={CountdownIcon}
                  label="剩余时间"
                  value={task.eta_seconds ? formatTime(task.eta_seconds) : 'N/A'}
                />
              </div>
            </div>

            {/* 训练日志 */}
            <div className="relative flex-1 min-h-0">
              {/* WebSocket状态指示器 */}
              <div className="absolute top-3 right-3 z-10">
                <div className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`}></div>
              </div>
              <div
                ref={logContainerRef}
                className="rounded-3xl bg-black text-white font-mono text-xs p-3 h-full overflow-auto"
                onScroll={(e) => {
                  const el = e.currentTarget;
                  const threshold = 10; // 距离底部阈值像素
                  const isAtBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - threshold;
                  setAutoFollow(isAtBottom);
                }}
              >
                {logs.length === 0 ? (
                  <div className="text-gray-400">暂无日志...</div>
                ) : (
                  logs.map((line, idx) => (
                    <div key={idx}>{line}</div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {selectedTab === "metrics" && (
          <div className="flex-1 overflow-hidden">
            <TrainingMetricsView taskId={id!} />
          </div>
        )}

        {selectedTab === "samples" && (
          <div className="flex-1 overflow-auto">
            <TaskSamplesView taskId={id!} refreshSignal={samplesRefreshTick} />
          </div>
        )}
      </div>

      {/* Runtime 安装对话框 */}
      <RuntimeInstallModal
        isOpen={showRuntimeModal}
        onClose={() => setShowRuntimeModal(false)}
        onSuccess={() => handleControl('start')}
      />
    </div>
  );
}

// 时间格式化函数
function formatTime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  } else {
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }
}




