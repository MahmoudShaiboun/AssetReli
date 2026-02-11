import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8002';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getDashboard = async () => {
  const response = await api.get('/dashboard');
  return response.data;
};

export const getPredictions = async (limit = 100) => {
  const response = await api.get(`/predictions?limit=${limit}`);
  return response.data;
};

export const createPrediction = async (features: any) => {
  const response = await api.post('/predictions', { features });
  return response.data;
};

export const submitFeedback = async (feedbackData: any) => {
  const response = await api.post('/feedback', feedbackData);
  return response.data;
};

export const triggerRetrain = async (selectedDataIds: any = null) => {
  const response = await api.post('/retrain', { selected_data_ids: selectedDataIds });
  return response.data;
};

export const getSensors = async () => {
  const response = await api.get('/sensors');
  return response.data;
};

export const getSensorData = async (sensorId: string, limit = 100) => {
  const response = await api.get(`/sensors/${sensorId}/data?limit=${limit}`);
  return response.data;
};

// WebSocket connection for real-time data
export const connectWebSocket = (onMessage: (data: any) => void) => {
  const ws = new WebSocket(`${WS_URL}/stream`);
  
  ws.onopen = () => {
    console.log('WebSocket connected');
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
  
  ws.onclose = () => {
    console.log('WebSocket disconnected');
  };
  
  return ws;
};

export default api;
