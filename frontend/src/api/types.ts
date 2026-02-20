export interface SensorReading {
  _id: string;
  sensor_id: string;
  timestamp: string;
  temperature?: number;
  vibration?: number;
  pressure?: number;
  humidity?: number;
  motor_data?: any;
  pump_data?: any;
  full_features?: number[];
  has_feedback: boolean;
  prediction?: string;
  confidence?: number;
  fault_label?: string;
  state?: string;
}

export interface Sensor {
  id: string;
  tenant_id: string;
  asset_id: string;
  gateway_id?: string;
  sensor_code: string;
  sensor_type: string;
  mount_location?: string;
  mqtt_topic?: string;
  is_active: boolean;
  created_at?: string;
}

export interface SensorData {
  topic: string;
  data: {
    sensor_id?: string;
    temperature?: number;
    vibration?: number;
    pressure?: number;
    humidity?: number;
    timestamp?: string;
    state?: string;
    regime?: string;
    fault_label?: string;
    motor_DE_vib_band_1?: number;
    motor_DE_vib_band_2?: number;
    motor_DE_vib_band_3?: number;
    motor_DE_vib_band_4?: number;
    motor_DE_temp_c?: number;
    motor_NDE_temp_c?: number;
    motor_DE_ultra_db?: number;
    motor_NDE_ultra_db?: number;
    pump_DE_vib_band_1?: number;
    pump_DE_vib_band_2?: number;
    pump_DE_vib_band_3?: number;
    pump_DE_vib_band_4?: number;
    pump_DE_temp_c?: number;
    pump_NDE_temp_c?: number;
    pump_DE_ultra_db?: number;
    pump_NDE_ultra_db?: number;
  };
  timestamp: string;
}

export interface HistoricalData {
  timestamp: string;
  motor_temp: number;
  motor_vib: number;
  pump_temp: number;
  pump_ultra: number;
  prediction?: string;
  confidence?: number;
  sensor_id?: string;
}

export interface FaultAction {
  id: string;
  type: 'email' | 'webhook' | 'sms' | 'slack';
  enabled: boolean;
  config: {
    email?: string;
    url?: string;
    phone?: string;
    channel?: string;
  };
}
