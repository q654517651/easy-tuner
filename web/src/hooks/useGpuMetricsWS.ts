import { useCallback, useEffect, useRef } from 'react';

interface UseGpuMetricsWSOptions {
  enabled: boolean;
  onUpdate: (gpus: any[]) => void;
}

export function useGpuMetricsWS({ enabled, onUpdate }: UseGpuMetricsWSOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const connTokenRef = useRef(0);
  const reconnectTimer = useRef<number | null>(null);
  const reconnectAttempts = useRef(0);

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current) {
      try {
        const ws = wsRef.current;
        if (ws.readyState === WebSocket.OPEN) ws.close(1000);
      } catch {}
      wsRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!enabled) return;
    const attempts = reconnectAttempts.current;
    if (attempts > 6) return; // 上限
    const base = 500;
    const delay = Math.min(2000, base * Math.pow(2, attempts));
    reconnectTimer.current = window.setTimeout(() => {
      if (enabled) connect();
    }, delay);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  const connect = useCallback(() => {
    if (!enabled || wsRef.current) return;
    const myToken = ++connTokenRef.current;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const envBaseRaw = (import.meta as any)?.env?.VITE_WS_BASE as string | undefined;
    const cleaned = envBaseRaw?.trim()?.replace(/^wss?:\/\//i, '');
    const isDev = (import.meta as any)?.env?.DEV;
    const isNonBackendPort = typeof location !== 'undefined' && location.port && location.port !== '8000';
    const baseHost = (cleaned && cleaned.length > 0) ? cleaned : (isDev && isNonBackendPort ? '127.0.0.1:8000' : (location.host || '127.0.0.1:8000'));
    const url = `${proto}//${baseHost}/ws/system/gpu`;
    const DEBUG = ((import.meta as any)?.env?.VITE_DEBUG_WS === 'true') || (typeof localStorage !== 'undefined' && localStorage.getItem('VITE_DEBUG_WS') === 'true');
    if (DEBUG) try { console.info('[WS][gpu] connect', url); } catch {}

    const ws = new WebSocket(url);
    ws.onopen = () => {
      if (connTokenRef.current !== myToken) return;
      reconnectAttempts.current = 0;
      if (DEBUG) try { console.info('[WS][gpu] open'); } catch {}
    };
    ws.onmessage = (e) => {
      if (connTokenRef.current !== myToken) return;
      try {
        const msg = JSON.parse(e.data);
        if (msg?.type === 'gpu_metrics') {
          const g = msg.payload?.gpus || [];
          onUpdate(g);
        }
      } catch {}
    };
    ws.onclose = (ev) => {
      if (connTokenRef.current !== myToken) return;
      wsRef.current = null;
      if (DEBUG) try { console.info('[WS][gpu] close', ev.code, ev.reason); } catch {}
      if (ev.code === 1000 || ev.code === 1001) return;
      reconnectAttempts.current += 1;
      scheduleReconnect();
    };
    ws.onerror = () => {
      if (connTokenRef.current !== myToken) return;
      if (DEBUG) try { console.warn('[WS][gpu] error'); } catch {}
    };
    wsRef.current = ws;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, onUpdate]);

  useEffect(() => {
    if (enabled && document.visibilityState === 'visible' && navigator.onLine) {
      connect();
    } else {
      cleanup();
    }
    return cleanup;
  }, [enabled, connect, cleanup]);

  useEffect(() => {
    const vis = () => {
      if (document.visibilityState === 'hidden') cleanup();
      else if (enabled && !wsRef.current) connect();
    };
    const online = () => {
      if (navigator.onLine && enabled && !wsRef.current) connect();
      else cleanup();
    };
    document.addEventListener('visibilitychange', vis);
    window.addEventListener('online', online);
    window.addEventListener('offline', online);
    return () => {
      document.removeEventListener('visibilitychange', vis);
      window.removeEventListener('online', online);
      window.removeEventListener('offline', online);
    };
  }, [enabled, connect, cleanup]);
}

