import type { TrainTask } from "../data/tasks";
import { useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { addToast, Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button, useDisclosure, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from "@heroui/react";
import { trainingApi } from "../services/api";
import MoreIcon from "@/assets/icon/more.svg?react";
import { useTrainingWebSocket } from "../hooks/useTrainingWebSocket";

function StatusPill({ s }: { s: TrainTask["status"] }) {
  const map: Record<TrainTask["status"], { label: string; cls: string }> = {
    pending:   { label: "⏳ 等待中", cls: "bg-neutral-200 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300" },
    running:   { label: "▶️ 训练中", cls: "bg-sky-100 dark:bg-sky-900/50 text-sky-600 dark:text-sky-400" },
    completed: { label: "✅ 已完成", cls: "bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-400" },
    failed:    { label: "❌ 失败",   cls: "bg-rose-100 dark:bg-rose-900/50 text-rose-700 dark:text-rose-400" },
    cancelled: { label: "⏹️ 已取消", cls: "bg-amber-100 dark:bg-amber-900/50 text-amber-600 dark:text-amber-400" },
  };

  // 添加安全检查，防止 undefined 或无效状态
  const m = map[s] || { label: "未知", cls: "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300" };

  return (
    <span className={`px-2 h-7 inline-flex items-center rounded-lg text-xs ${m.cls}`}>
      {m.label}
    </span>
  );
}

export default function TaskRow({ task, onTaskDeleted }: { task: TrainTask; onTaskDeleted?: () => void }) {
  // 添加安全检查，防止 task 或其属性为 undefined
  if (!task) {
    return null;
  }

  // 行内实时指标（由 WS 周期刷新覆盖 task.json 值）
  const [rowMetrics, setRowMetrics] = useState<{ step?: number; total?: number; speed?: number; speedUnit?: string; etaSeconds?: number }>({});
  const [visible, setVisible] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const pendingRef = useRef<{ step?: number; total?: number; speed?: number; speedUnit?: string; etaSeconds?: number }>({});
  const flushTimerRef = useRef<number | null>(null);
  const isRunning = task.status === 'running';
  const pct = Math.min(
    100,
    Math.round(
      ((rowMetrics.step ?? task.done ?? 0) / (rowMetrics.total ?? task.total ?? 1)) * 100
    )
  );
  const navigate = useNavigate();
  const [isDeleting, setIsDeleting] = useState(false);
  const { isOpen, onOpen, onClose } = useDisclosure();

  const handleDeleteClick = () => {
    onOpen();
  };

  const handleDropdownAction = (key: React.Key) => {
    if (key === "delete") {
      handleDeleteClick();
    }
    // 可以在这里添加其他动作，如编辑、暂停等
  };

  const handleConfirmDelete = async () => {
    try {
      setIsDeleting(true);
      await trainingApi.deleteTask(task.id);
      onClose();
      addToast({
        title: "删除成功",
        description: `训练任务"${task.name}"已删除`,
        color: "success",
        timeout: 3000
      });
      if (onTaskDeleted) {
        onTaskDeleted();
      }
    } catch (error) {
      addToast({
        title: "删除失败",
        description: `删除任务失败: ${error}`,
        color: "danger",
        timeout: 3000
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // 可见性观察：仅在卡片进入视口时启用 WS
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.target === el) {
          setVisible(e.isIntersecting);
        }
      }
    }, { root: null, threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // 周期性把 pending 刷到 state，降低渲染频率
  useEffect(() => {
    if (flushTimerRef.current) {
      clearInterval(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    flushTimerRef.current = window.setInterval(() => {
      if (!pendingRef.current) return;
      const p = pendingRef.current;
      if (p.step === undefined && p.total === undefined && p.speed === undefined && p.speedUnit === undefined && p.etaSeconds === undefined) return;
      setRowMetrics(prev => ({
        step: p.step ?? prev.step,
        total: p.total ?? prev.total,
        speed: p.speed ?? prev.speed,
        speedUnit: p.speedUnit ?? prev.speedUnit,
        etaSeconds: p.etaSeconds ?? prev.etaSeconds,
      }));
      // 清空已消费
      pendingRef.current = {};
    }, 1500);
    return () => {
      if (flushTimerRef.current) {
        clearInterval(flushTimerRef.current);
        flushTimerRef.current = null;
      }
      pendingRef.current = {};
    };
  }, [task.id]);

  // 复用主 Hook 建连（仅 metrics），按可见性+运行态启用
  useTrainingWebSocket({
    taskId: task.id,
    isRunning,
    taskState: isRunning ? 'running' : task.status,
    tab: 'metrics',
    enabled: isRunning && visible && document.visibilityState === 'visible' && navigator.onLine,
    onMessage: (message: any) => {
      if (message?.type !== 'metric') return;
      const p = message.payload || {};
      if (typeof p.step === 'number') pendingRef.current.step = p.step;
      if (typeof p.total_steps === 'number') pendingRef.current.total = p.total_steps;
      if (typeof p.speed === 'number') pendingRef.current.speed = p.speed;
      if (p.speed_unit) pendingRef.current.speedUnit = p.speed_unit;
      if (typeof p.eta_seconds === 'number') pendingRef.current.etaSeconds = p.eta_seconds;
    }
  });

  const displayThroughput = (rowMetrics.speed ?? task.throughput ?? 0).toFixed(2);
  const displayThroughputUnit = rowMetrics.speedUnit ?? task.throughputUnit ?? 'it/s';
  const displayEta = (() => {
    const s = rowMetrics.etaSeconds ?? task.eta;
    if (typeof s === 'number') {
      const hours = Math.floor(s / 3600);
      const minutes = Math.floor((s % 3600) / 60);
      return hours > 0 ? `${hours}h ${minutes}min` : `${minutes}min`;
    }
    return task.eta || '';
  })();

  return (
    <div
      ref={containerRef}
      onClick={() => navigate(`/tasks/${task.id}`)}   // ⬅️ 整个卡片可点
      className="group relative rounded-2xl p-4 sm:p-5 flex items-start gap-3 cursor-pointer hover:bg-neutral-200/50 dark:hover:bg-white/10 transition"
      style={{ backgroundColor: 'var(--bg2)' }}
    >
      {/* 左侧图标 */}
      <div className="w-12 h-12 rounded-xl bg-sky-500/15 text-sky-600 grid place-items-center text-xl shrink-0">
        🧊
      </div>

      {/* 中部文本 */}
      <div className="flex-1 min-w-0">
        <div className="font-semibold truncate">{task.name || "未知任务"}</div>

        <div className="mt-1 flex items-center gap-2">
          <StatusPill s={task.status} />
          <span className="px-2 h-7 inline-flex items-center rounded-lg text-xs bg-neutral-200/80 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
            {task.model || "未知模型"}
          </span>
          <span className="px-2 h-7 inline-flex items-center rounded-lg text-xs bg-neutral-200/80 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
            {task.createdAt || "未知日期"}
          </span>
        </div>

        {/* 进度条和进度信息 */}
        <div className="mt-4">
          <div className="h-1.5 rounded-full bg-neutral-200/80 dark:bg-white/10 overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-[width] duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between text-xs opacity-60">
            <span>{(rowMetrics.step ?? task.done) || 0}/{(rowMetrics.total ?? task.total) || 0}</span>
            <span>{displayThroughput} {displayThroughputUnit} · {displayEta || ""}</span>
          </div>
        </div>
      </div>

      {/* 更多按钮位 */}
      <div
        className="absolute top-2 right-2"
        onClick={(e) => e.stopPropagation()}
      >
        <Dropdown placement="bottom-end">
          <DropdownTrigger>
            <Button
              isIconOnly
              variant="light"
              size="sm"
              className="w-9 h-9"
            >
              <span className="flex items-center justify-center w-6 h-6 [&>svg]:w-6 [&>svg]:h-6 [&_path]:fill-current text-gray-700 dark:text-gray-300">
                <MoreIcon />
              </span>
            </Button>
          </DropdownTrigger>
          <DropdownMenu
            aria-label="任务操作"
            onAction={handleDropdownAction}
          >
            <DropdownItem
              key="delete"
              className="text-danger"
              color="danger"
              startContent="🗑️"
            >
              删除任务
            </DropdownItem>
          </DropdownMenu>
        </Dropdown>
      </div>

      {/* 删除确认Modal */}
      <Modal isOpen={isOpen} onClose={onClose} placement="center">
        <ModalContent>
          <ModalHeader className="flex flex-col gap-1">
            确认删除
          </ModalHeader>
          <ModalBody>
            <p>确定要删除训练任务 <strong>"{task.name}"</strong> 吗？</p>
            <p className="text-sm text-gray-500">此操作不可撤销，所有相关的训练数据和记录都将被永久删除。</p>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="light"
              onPress={onClose}
              disabled={isDeleting}
            >
              取消
            </Button>
            <Button
              color="danger"
              onPress={handleConfirmDelete}
              disabled={isDeleting}
              isLoading={isDeleting}
            >
              {isDeleting ? "删除中..." : "确认删除"}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}
