import { WS_URL } from '../config';

export const connectWebSocket = (onMessage: (data: any) => void): WebSocket => {
  const token = localStorage.getItem('aastreli_token');
  const url = token ? `${WS_URL}/stream?token=${token}` : `${WS_URL}/stream`;
  const ws = new WebSocket(url);

  ws.onopen = () => {
    console.log('WebSocket connected');
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error('WebSocket message parse error:', e);
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  ws.onclose = (event) => {
    console.log('WebSocket disconnected', event.code === 4001 ? '(auth failed)' : '');
  };

  return ws;
};
