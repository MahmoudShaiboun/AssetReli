import axios from 'axios';
import { API_URL } from '../config';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT token and tenant ID to every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('aastreli_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const tenantId = localStorage.getItem('aastreli_tenant_id');
  if (tenantId) {
    config.headers['X-Tenant-Id'] = tenantId;
  }
  return config;
});

export const getDashboard = async () => {
  const response = await apiClient.get('/dashboard');
  return response.data;
};

export const getPredictions = async (limit = 100) => {
  const response = await apiClient.get(`/predictions?limit=${limit}`);
  return response.data;
};

export const createPrediction = async (features: any) => {
  const response = await apiClient.post('/predictions', { features });
  return response.data;
};

export const submitFeedback = async (feedbackData: any) => {
  const response = await apiClient.post('/feedback', feedbackData);
  return response.data;
};

export const triggerRetrain = async (selectedDataIds: any = null) => {
  const response = await apiClient.post('/retrain', { selected_data_ids: selectedDataIds });
  return response.data;
};

export const getSensors = async (assetId?: string) => {
  const params = assetId ? { asset_id: assetId } : {};
  const response = await apiClient.get('/sensors', { params });
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
  const response = await apiClient.post('/sensors', data);
  return response.data;
};

export const getSensorData = async (sensorCode: string, limit = 100) => {
  const response = await apiClient.get(`/sensor-data/${sensorCode}?limit=${limit}`);
  return response.data;
};

export default apiClient;
