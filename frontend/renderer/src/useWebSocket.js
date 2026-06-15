// WebSocket hook：连接 /ws/events，指数退避重连（spec 04 功能4 场景2），
// 维护连接态 + 最近事件列表。组件订阅事件做实时更新。
import { useEffect, useRef, useState, useCallback } from 'react';
import { WS_URL } from './api.js';

const MAX_BACKOFF = 30000;

export function useWebSocket(onEvent) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState([]);
  const wsRef = useRef(null);
  const backoffRef = useRef(1000);
  const timerRef = useRef(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    let ws;
    try {
      ws = new WebSocket(WS_URL);
    } catch {
      scheduleReconnect();
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      backoffRef.current = 1000; // 重连成功 → 退避重置
    };
    ws.onmessage = (e) => {
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      setEvents((prev) => [msg, ...prev].slice(0, 100));
      if (onEventRef.current) onEventRef.current(msg);
    };
    ws.onclose = () => {
      setConnected(false);
      scheduleReconnect();
    };
    ws.onerror = () => ws.close();

    function scheduleReconnect() {
      if (timerRef.current) return;
      const delay = Math.min(backoffRef.current, MAX_BACKOFF);
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF);
        connect();
      }, delay);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // 卸载时不触发重连
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { connected, events };
}
