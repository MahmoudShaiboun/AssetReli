import { useState, useEffect, useRef } from 'react';
import { connectWebSocket } from '../api/websocket';

export default function useWebSocket() {
  const [data, setData] = useState<Record<string, any>>({});
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    // Defer to avoid React 18 StrictMode double-mount teardown
    const timer = setTimeout(() => {
      if (cancelled) return;

      wsRef.current = connectWebSocket((incoming) => {
        if (!cancelled) {
          setData(incoming);
          setConnected(true);
        }
      });

      wsRef.current.onclose = () => {
        if (!cancelled) setConnected(false);
      };
    }, 0);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return { data, connected };
}
