import React, { useEffect, useState } from 'react';
import {
  Container,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Box,
  Chip,
  CircularProgress,
  Alert
} from '@mui/material';
import { connectWebSocket } from '../services/api';

interface SensorData {
  topic: string;
  data: {
    sensor_id?: string;
    temperature?: number;
    vibration?: number;
    pressure?: number;
    humidity?: number;
    // Complex schema fields (sensors/data)
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

export default function RealtimeData() {
  const [sensorData, setSensorData] = useState<Record<string, SensorData>>({});
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;

    try {
      ws = connectWebSocket((data: Record<string, SensorData>) => {
        setSensorData(data);
        setConnected(true);
        setError(null);
      });

      return () => {
        if (ws) {
          ws.close();
        }
      };
    } catch (err) {
      setError('Failed to connect to real-time data stream');
      console.error('WebSocket error:', err);
    }
  }, []);

  const formatValue = (value: number | undefined) => {
    return value !== undefined ? value.toFixed(2) : 'N/A';
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  // Extract display values based on data schema
  const extractDisplayData = (item: SensorData) => {
    const data = item.data;
    
    // Check if this is complex schema (sensors/data)
    if (data.motor_DE_vib_band_1 !== undefined) {
      return {
        sensorId: 'Industrial Sensor',
        temperature: data.motor_DE_temp_c,
        vibration: data.motor_DE_vib_band_1,
        pressure: data.pump_DE_ultra_db,
        humidity: data.pump_DE_temp_c,
        state: data.state,
        faultLabel: data.fault_label
      };
    }
    
    // Simple schema (sensors/industrial/data)
    return {
      sensorId: data.sensor_id || 'Unknown',
      temperature: data.temperature,
      vibration: data.vibration,
      pressure: data.pressure,
      humidity: data.humidity,
      state: undefined,
      faultLabel: undefined
    };
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4">
          Real-time Sensor Data
        </Typography>
        <Chip 
          label={connected ? "Connected" : "Disconnected"} 
          color={connected ? "success" : "error"}
          sx={{ ml: 2 }}
        />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {!connected && !error && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {connected && Object.keys(sensorData).length === 0 && (
        <Alert severity="info">
          Waiting for sensor data... Make sure MQTT sensors are publishing data.
        </Alert>
      )}

      {Object.keys(sensorData).length > 0 && (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell><strong>Sensor ID</strong></TableCell>
                <TableCell><strong>Motor Temp (°C)</strong></TableCell>
                <TableCell><strong>Motor Vib (Hz)</strong></TableCell>
                <TableCell><strong>Pump Ultra (dB)</strong></TableCell>
                <TableCell><strong>Pump Temp (°C)</strong></TableCell>
                <TableCell><strong>Status</strong></TableCell>
                <TableCell><strong>Last Update</strong></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.values(sensorData).map((item, idx) => {
                const displayData = extractDisplayData(item);
                return (
                  <TableRow key={idx} hover>
                    <TableCell>{displayData.sensorId}</TableCell>
                    <TableCell>{formatValue(displayData.temperature)}</TableCell>
                    <TableCell>{formatValue(displayData.vibration)}</TableCell>
                    <TableCell>{formatValue(displayData.pressure)}</TableCell>
                    <TableCell>{formatValue(displayData.humidity)}</TableCell>
                    <TableCell>
                      {displayData.faultLabel && (
                        <Chip 
                          label={displayData.faultLabel}
                          color={displayData.faultLabel === 'normal' ? 'success' : 'warning'}
                          size="small"
                        />
                      )}
                      {displayData.state && !displayData.faultLabel && (
                        <Chip label={displayData.state} size="small" />
                      )}
                      {!displayData.state && !displayData.faultLabel && 'N/A'}
                    </TableCell>
                    <TableCell>{formatTimestamp(item.timestamp)}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Alert severity="info" sx={{ mt: 3 }}>
        <strong>Note:</strong> This data is streamed in real-time from MQTT sensors. 
        All readings are automatically stored in the database and can be viewed in the Feedback section.
      </Alert>
    </Container>
  );
}
