import { useState, useEffect, useRef, useCallback } from 'react';

interface TrainingWebSocketOptions {
  taskId: string;
  isRunning: boolean;
  taskState?: string;  // Phase 1 新增：用于终态判断，Phase 2 将统一为任务对象
  tab: string;
  sinceStep?: number;
  sinceOffset?: number;
  onMessage?: (message: any) => void;
  onFinal?: (status: string) => void;
  enabled?: boolean; // 新增：允许外部禁用本 Hook 的建连
}

// 重连控制常量
const MAX_RECONNECT_ATTEMPTS = 3;
const BASE_BACKOFF_MS = 300;
const MAX_BACKOFF_MS = 2000;

export function useTrainingWebSocket({
  taskId,
  isRunning,
  taskState,  // Phase 1 新增
  tab,
  sinceStep = 0,
  sinceOffset = 0,
  onMessage,
  onFinal,
  enabled = true
}: TrainingWebSocketOptions) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const connTokenRef = useRef(0);
  const reconnectTimer = useRef<number>();
  const heartbeatTimer = useRef<number>();
  // 保存最新的 since 值，避免把 sinceOffset/sinceStep 放进 connect 的依赖导致重连抖动
  const sinceOffsetRef = useRef(sinceOffset);
  const sinceStepRef = useRef(sinceStep);
  // 简化：移除HTTP探活与final状态，本地仅依赖state消息与shouldConnect
  const reconnectAttempts = useRef(0);
  const shouldReconnectRef = useRef(true);
  const doConnectRef = useRef<() => void>(() => {});

  // 跟随外部更新 since 引用（不触发重连）
  useEffect(() => { sinceOffsetRef.current = sinceOffset; }, [sinceOffset]);
  useEffect(() => { sinceStepRef.current = sinceStep; }, [sinceStep]);

  // ==================== Phase 1 修复：终态重连问题 ====================
  // TODO Phase 2: 移除 isRunning 参数，改为基于统一状态管理器判断
  // 终态定义（符合新架构规范）
  const TERMINAL_STATES = ['completed', 'failed', 'cancelled'];
  const isTerminalState = taskState ? TERMINAL_STATES.includes(taskState) : false;

  // 判断是否需要连接（增加终态检查）
  const shouldConnect =
    enabled &&
    isRunning &&
    !isTerminalState &&  // 新增：终态不连接（解决用户反馈的重连问题）
    document.visibilityState === 'visible' &&
    navigator.onLine;

  // 连接状态变化日志
  // 静默：不在控制台打印连接建议变更，避免噪音

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = undefined;
    }
    if (heartbeatTimer.current) {
      clearTimeout(heartbeatTimer.current);
      heartbeatTimer.current = undefined;
    }
    if (wsRef.current) {
      try {
        const ws = wsRef.current;
        // 避免在 CONNECTING 阶段直接关闭导致握手错误；在 open 后立即关闭
        if (ws.readyState === WebSocket.CONNECTING) {
          try {
            ws.addEventListener('open', () => {
              try { ws.close(1000); } catch {}
            }, { once: true });
          } catch {}
        } else if (ws.readyState === WebSocket.OPEN) {
          ws.close(1000);
        }
      } catch {}
      wsRef.current = null;
    }
    setConnected(false);
    shouldReconnectRef.current = false;
  }, []);


  // 然后定义 scheduleReconnectWithBackoff（在 connect 之前），通过 ref 调用最新 connect
  const scheduleReconnectWithBackoff = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = undefined;
    }
    if (!shouldReconnectRef.current) {
      // 静默：停止重连提示
      return;
    }
    const attempts = reconnectAttempts.current;
    if (attempts >= MAX_RECONNECT_ATTEMPTS) {
      // 静默：达到最大重连次数
      shouldReconnectRef.current = false;
      return;
    }
    reconnectAttempts.current = attempts + 1;

    // 指数退避 + 抖动
    const exp = Math.min(BASE_BACKOFF_MS * Math.pow(2, attempts), MAX_BACKOFF_MS);
    const jitter = Math.floor(Math.random() * 200);
    const delay = exp + jitter;

    // 静默：重连退避日志
    reconnectTimer.current = window.setTimeout(() => {
      if (shouldReconnectRef.current) {
        doConnectRef.current(); // ← 调用当前最新的 connect
      }
    }, delay);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current || !shouldConnect) return;

    // 生成本次连接的token，用于隔离多实例竞态
    const myToken = ++connTokenRef.current;

    // 构建WebSocket URL - 根据tab映射到对应的WebSocket端点
    const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const envBaseRaw = (import.meta as any)?.env?.VITE_WS_BASE as string | undefined;
    // 支持写完整 ws:// 或仅 host:port
    const cleanedEnvBase = envBaseRaw?.trim()?.replace(/^wss?:\/\//i, '');
    // 不在URL上附带 since 参数，避免URL变化导致的重连抖动；
    // 历史偏移在 onopen 后用一条 request_history 发送。

    // 将前端tab映射到后端WebSocket端点
    const wsEndpoint = (() => {
      switch (tab) {
        case 'progress': return 'logs';      // progress页面需要日志推送
        case 'metrics': return 'metrics';    // metrics页面需要指标推送
        case 'samples': return 'samples';    // samples页面需要文件推送
        default: return 'logs';              // 默认使用logs端点
      }
    })();

    // 基址选择顺序：VITE_WS_BASE -> 若本地开发端口非8000则兜底 127.0.0.1:8000 -> location.host
    const isDev = (import.meta as any)?.env?.DEV;
    const isNonBackendPort = typeof location !== 'undefined' && location.port && location.port !== '8000';
    const baseHost = (cleanedEnvBase && cleanedEnvBase.length > 0)
      ? cleanedEnvBase
      : (isDev && isNonBackendPort ? '127.0.0.1:8000' : (location.host || '127.0.0.1:8000'));
    const wsUrl = `${wsProtocol}//${baseHost}/ws/training/${taskId}/${wsEndpoint}`;
    // 调试开关：优先环境变量，其次本地存储（可在浏览器控制台随时开启：localStorage.setItem('VITE_DEBUG_WS','true')）
    const DEBUG = ((import.meta as any)?.env?.VITE_DEBUG_WS === 'true') ||
                  (typeof localStorage !== 'undefined' && localStorage.getItem('VITE_DEBUG_WS') === 'true');
    if (DEBUG) {
      try { console.info('[WS] connecting to', wsUrl, 'shouldConnect=', shouldConnect); } catch {}
    }

    const websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
      if (connTokenRef.current !== myToken) return; // 过期实例
      // 静默：连接成功
      if (DEBUG) try { console.info('[WS open]', wsUrl); } catch {}
      setConnected(true);
      reconnectAttempts.current = 0; // 成功建立连接时清零

      // 主动请求历史数据（根据当前tab）
      try {
        if (tab === 'metrics') {
          websocket.send(JSON.stringify({ type: 'request_history', data_type: 'metrics' }));
        } else {
          // 默认请求历史日志（用最新的偏移，不依赖闭包中的旧值）
          websocket.send(JSON.stringify({
            type: 'request_history',
            data_type: 'logs',
            since_offset: sinceOffsetRef.current || 0,
          }));
        }
      } catch (e) {
        // 历史请求失败保留错误
        console.error('请求历史数据发送失败:', e);
      }
    };

    websocket.onmessage = (event) => {
      if (connTokenRef.current !== myToken) return; // 过期实例
      try {
        const message = JSON.parse(event.data);
        // 静默：消息体打印
        if (DEBUG) try { console.info('[WS msg]', message?.type ?? 'unknown'); } catch {}

        // 任意收到数据都认为连接健康，清零计数（避免误触上限）
        if (message?.type === 'state' || message?.type === 'log' || message?.type === 'historical_logs' || message?.type === 'connected') {
          reconnectAttempts.current = 0;
        }

        // 状态消息到达终态（唯一通道）
        if (message.type === 'state') {
          const toState = message.payload?.to_state || message.payload?.current_state;
          if (toState && ['completed', 'failed', 'cancelled'].includes(toState)) {
            shouldReconnectRef.current = false;
            if (reconnectTimer.current) {
              clearTimeout(reconnectTimer.current);
              reconnectTimer.current = undefined;
            }
            onFinal?.(toState);
            websocket.close(1000);
            return;
          }
        }

        onMessage?.(message);
      } catch (error) {
        console.error('WebSocket消息解析失败:', error, 'Raw data:', event.data);
      }
    };

    websocket.onclose = async (event) => {
      const isStale = connTokenRef.current !== myToken;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = undefined;
      }
      // 静默：连接关闭
      if (DEBUG) try { console.info('[WS closed]', event.code, event.reason, (event as any).wasClean, 'url=', wsUrl, 'shouldConnect=', shouldConnect); } catch {}
      // 无论是否过期实例，都要清理当前引用（如匹配）
      if (wsRef.current === websocket) {
        wsRef.current = null;
      }
      if (isStale) {
        return;
      }
      setConnected(false);

      // 关闭：若仍处于活跃态则重连，否则停止
      // 仅对异常关闭（非 1000/1001）尝试退避重连
      if (event.code === 1000 || event.code === 1001) {
        return;
      }

      // 仅在仍处于活跃态且允许重连时尝试
      if (shouldReconnectRef.current && !isTerminalState && shouldConnect) {
        scheduleReconnectWithBackoff();
      }
    };

    websocket.onerror = () => {
      // 过期实例不再触发逻辑，但清理引用
      if (connTokenRef.current !== myToken) {
        if (wsRef.current === websocket) wsRef.current = null;
        return;
      }
      if (DEBUG) try { console.warn('[WS error]', wsUrl); } catch {}
      // 静默：错误提示，统一在 onclose 处理
      // 不直接重连，等待 onclose 流程统一处理
    };

    wsRef.current = websocket;
  }, [taskId, tab, shouldConnect, sinceStep, sinceOffset, onMessage, onFinal, isTerminalState]);

  // 用 useEffect 保持 ref 指向最新 connect，打破依赖循环
  useEffect(() => {
    doConnectRef.current = connect;
  }, [connect]);


  // 主要连接逻辑
  useEffect(() => {
    if (!taskId) return;

    // 重置重连状态（仅在允许连接时）
    if (shouldConnect) {
      shouldReconnectRef.current = true;
      reconnectAttempts.current = 0;
      // 通过 ref 调用当前 connect，避免把 connect 放进依赖导致抖动
      doConnectRef.current();
    } else {
      cleanup();
    }

    return cleanup;
  }, [taskId, shouldConnect, cleanup]);

  // 当同一任务从终态恢复到 running（重试）时，尝试重连
  useEffect(() => {
    if (!taskId) return;
    if (taskState === 'running') {
      shouldReconnectRef.current = true;
      reconnectAttempts.current = 0;
      if (shouldConnect && !wsRef.current) {
        doConnectRef.current();
      }
    }
  }, [taskId, taskState, shouldConnect]);

  // 监听页面状态变化
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        cleanup();
      } else if (shouldConnect && !wsRef.current) {
        connect();
      }
    };

    const handleOnlineChange = () => {
      if (navigator.onLine && shouldConnect && !wsRef.current) {
        connect();
      } else if (!navigator.onLine) {
        cleanup();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('online', handleOnlineChange);
    window.addEventListener('offline', handleOnlineChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('online', handleOnlineChange);
      window.removeEventListener('offline', handleOnlineChange);
    };
  }, [shouldConnect, connect, cleanup]);

  return { connected };
}
