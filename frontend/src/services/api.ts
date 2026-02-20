import axios from 'axios';
import { API_URL, WS_URL } from '../config';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('aastreli_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
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

export const getSensors = async (assetId?: string) => {
  const params = assetId ? { asset_id: assetId } : {};
  const response = await api.get('/sensors', { params });
  return response.data;
};

export const createSensor = async (data: {
  asset_id: string;
  sensor_code: string;
  sensor_type: string;
  gateway_id?: string;
  mount_location?: string;
  mqtt_topic?: string;
}) => {
  const response = await api.post('/sensors', data);
  return response.data;
};

export const getSensorData = async (sensorCode: string, limit = 100) => {
  const response = await api.get(`/sensor-data/${sensorCode}?limit=${limit}`);
  return response.data;
};

// WebSocket connection for real-time data
export const connectWebSocket = (onMessage: (data: any) => void) => {
  const ws = new WebSocket(`${WS_URL}/stream`);

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

  ws.onclose = () => {
    console.log('WebSocket disconnected');
  };

  return ws;
};

export default api;
