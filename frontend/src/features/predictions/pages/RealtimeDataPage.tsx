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
import { connectWebSocket } from '../../../api/websocket';
import { SensorData } from '../../../api/types';

export default function RealtimeDataPage() {
  const [sensorData, setSensorData] = useState<Record<string, SensorData>>({});
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;

    const timer = setTimeout(() => {
      if (cancelled) return;
      ws = connectWebSocket((data: Record<string, SensorData>) => {
        if (!cancelled) {
          setSensorData(data);
          setConnected(true);
          setError(null);
        }
      });

      ws.onerror = () => {
        if (!cancelled) setError('Failed to connect to real-time data stream');
      };

      ws.onclose = () => {
        if (!cancelled) setConnected(false);
      };
    }, 0);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (ws) ws.close();
    };
  }, []);

  const formatValue = (value: number | undefined) => value !== undefined ? value.toFixed(2) : 'N/A';
  const formatTimestamp = (timestamp: string) => new Date(timestamp).toLocaleTimeString();

  const extractDisplayData = (item: SensorData) => {
    const data = item.data;
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
        <Typography variant="h4">Real-time Sensor Data</Typography>
        <Chip label={connected ? "Connected" : "Disconnected"} color={connected ? "success" : "error"} sx={{ ml: 2 }} />
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {!connected && !error && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
      )}

      {connected && Object.keys(sensorData).length === 0 && (
        <Alert severity="info">Waiting for sensor data... Make sure MQTT sensors are publishing data.</Alert>
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
                        <Chip label={displayData.faultLabel} color={displayData.faultLabel === 'normal' ? 'success' : 'warning'} size="small" />
                      )}
                      {displayData.state && !displayData.faultLabel && <Chip label={displayData.state} size="small" />}
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
