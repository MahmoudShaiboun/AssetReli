import React, { useEffect, useState } from 'react';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  Box,
  Chip
} from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';
import { getDashboard, connectWebSocket } from '../services/api';
import api from '../services/api';

interface SensorData {
  topic: string;
  data: any;
  timestamp: string;
}

interface HistoricalData {
  timestamp: string;
  motor_temp: number;
  motor_vib: number;
  pump_temp: number;
  pump_ultra: number;
  prediction?: string;
  confidence?: number;
  sensor_id?: string;
}

export default function Dashboard() {
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [realtimeData, setRealtimeData] = useState<Record<string, SensorData>>({});
  const [historicalData, setHistoricalData] = useState<HistoricalData[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getDashboard();
        setDashboardData(data);
      } catch (error) {
        console.error('Error fetching dashboard:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);

    return () => clearInterval(interval);
  }, []);

  // Fetch historical data for graphs and recent predictions
  useEffect(() => {
    const fetchHistoricalData = async () => {
      try {
        const response = await api.get('/sensor-readings', {
          params: { skip: 0, limit: 50 }
        });
        const readings = response.data.readings || [];
        const chartData = readings.reverse().map((reading: any) => {
          // Parse timestamp as UTC, then format to local time
          let ts: string = reading.timestamp || '';
          if (!ts.endsWith('Z') && !ts.includes('+')) {
            ts += 'Z';
          }
          const date = new Date(ts);
          const timeStr = date.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
          });

          // Support both complex schema (motor_data/pump_data) and
          // simple schema (temperature/vibration/pressure/humidity)
          const motorTemp = reading.motor_data?.DE_temp ?? reading.temperature ?? 0;
          const motorVib = reading.motor_data?.DE_vib_band_1 ?? reading.vibration ?? 0;
          const pumpTemp = reading.pump_data?.DE_temp ?? reading.pressure ?? 0;
          const pumpUltra = reading.pump_data?.DE_ultra ?? reading.humidity ?? 0;

          return {
            timestamp: timeStr,
            motor_temp: motorTemp,
            motor_vib: motorVib,
            pump_temp: pumpTemp,
            pump_ultra: pumpUltra,
            prediction: reading.prediction,
            confidence: reading.confidence,
            sensor_id: reading.sensor_id
          };
        });
        setHistoricalData(chartData);
      } catch (error) {
        console.error('Error fetching historical data:', error);
      }
    };

    fetchHistoricalData();
    const interval = setInterval(fetchHistoricalData, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  // Connect to WebSocket for real-time data
  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;

    // Defer connection to avoid React 18 StrictMode double-mount teardown
    const timer = setTimeout(() => {
      if (cancelled) return;
      ws = connectWebSocket((data: Record<string, SensorData>) => {
        if (!cancelled) {
          setRealtimeData(data);
          setConnected(true);
        }
      });

      ws.onclose = () => {
        if (!cancelled) {
          setConnected(false);
        }
      };
    }, 0);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (ws) {
        ws.close();
      }
    };
  }, []);

  const getLatestRealtimeValues = () => {
    // Get latest prediction from historical data
    const latestPrediction = historicalData.length > 0 ? historicalData[historicalData.length - 1].prediction : null;
    
    // Try to get from real-time WebSocket data first for sensor values
    const wsData = Object.values(realtimeData)[0]?.data;
    if (wsData) {
      return {
        motorTemp: wsData.motor_DE_temp_c ?? wsData.temperature,
        motorVib: wsData.motor_DE_vib_band_1 ?? wsData.vibration,
        pumpTemp: wsData.pump_DE_temp_c ?? wsData.pressure,
        pumpUltra: wsData.pump_DE_ultra_db ?? wsData.humidity,
        prediction: latestPrediction,
        state: wsData.state
      };
    }
    
    // Fallback to latest historical data with prediction
    if (historicalData.length > 0) {
      const latest = historicalData[historicalData.length - 1];
      return {
        motorTemp: latest.motor_temp,
        motorVib: latest.motor_vib,
        pumpTemp: latest.pump_temp,
        pumpUltra: latest.pump_ultra,
        prediction: latest.prediction,
        state: null
      };
    }
    
    return null;
  };

  const latestValues = getLatestRealtimeValues();

  if (loading) return <Typography>Loading...</Typography>;

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">
          🏭 Industrial Anomaly Detection Dashboard
        </Typography>
        <Chip 
          label={connected ? "Real-time Connected" : "Offline"} 
          color={connected ? "success" : "error"}
        />
      </Box>
      
      <Grid container spacing={3}>
        {/* Stats Cards */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Total Predictions
              </Typography>
              <Typography variant="h3">
                {dashboardData?.total_predictions || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Feedback Collected
              </Typography>
              <Typography variant="h3">
                {dashboardData?.total_feedback || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={3}>
          <Card sx={{ bgcolor: latestValues?.prediction === 'normal' ? 'success.light' : 'warning.light' }}>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Latest ML Prediction
              </Typography>
              <Typography variant="h5">
                {latestValues?.prediction || 'Waiting...'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                System Health
              </Typography>
              <Typography variant="h3" color="success.main">
                ✓ Online
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Real-time Values */}
        {latestValues && (
          <>
            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Motor Temp
                  </Typography>
                  <Typography variant="h4">
                    {latestValues.motorTemp?.toFixed(1) || 'N/A'}°C
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Motor Vibration
                  </Typography>
                  <Typography variant="h4">
                    {latestValues.motorVib?.toFixed(2) || 'N/A'} Hz
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Pump Temp
                  </Typography>
                  <Typography variant="h4">
                    {latestValues.pumpTemp?.toFixed(1) || 'N/A'}°C
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Pump Ultrasonic
                  </Typography>
                  <Typography variant="h4">
                    {latestValues.pumpUltra?.toFixed(1) || 'N/A'} dB
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </>
        )}

        {/* Motor Temperature Chart */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Motor Temperature Trend
            </Typography>
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={historicalData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="motor_temp" stroke="#ff7300" fill="#ff7300" fillOpacity={0.6} name="Motor Temp (°C)" />
              </AreaChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Motor Vibration Chart */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Motor Vibration Trend
            </Typography>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={historicalData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="motor_vib" stroke="#8884d8" strokeWidth={2} name="Vibration (Hz)" />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Pump Temperature Chart */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Pump Temperature Trend
            </Typography>
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={historicalData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="pump_temp" stroke="#82ca9d" fill="#82ca9d" fillOpacity={0.6} name="Pump Temp (°C)" />
              </AreaChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Pump Ultrasonic Chart */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Pump Ultrasonic Trend
            </Typography>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={historicalData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="pump_ultra" stroke="#ffc658" strokeWidth={2} name="Ultrasonic (dB)" />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Recent Predictions with Anomalies Highlighted - Live Updates */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              🔮 Recent ML Predictions & Anomalies (Live)
            </Typography>
            <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
              {historicalData.length === 0 ? (
                <Typography variant="body2" color="textSecondary" sx={{ p: 2 }}>
                  Waiting for sensor data...
                </Typography>
              ) : (
                historicalData.slice(-15).reverse().map((reading, idx) => {
                  const isAnomaly = reading.prediction && reading.prediction.toLowerCase() !== 'normal';
                  return (
                    <Box 
                      key={idx} 
                      sx={{ 
                        p: 2, 
                        mb: 1, 
                        border: 1, 
                        borderColor: isAnomaly ? 'warning.main' : 'grey.300',
                        bgcolor: isAnomaly ? 'warning.light' : 'background.paper',
                        borderRadius: 1
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="body2">
                          <strong>Time:</strong> {reading.timestamp} | <strong>Sensor:</strong> {reading.sensor_id || 'N/A'}
                        </Typography>
                        <Box>
                          {isAnomaly && (
                            <Chip 
                              label="⚠️ ANOMALY" 
                              color="error"
                              size="small"
                              sx={{ mr: 1 }}
                            />
                          )}
                          <Chip 
                            label={reading.prediction || 'N/A'} 
                            color={reading.prediction?.toLowerCase() === 'normal' ? 'success' : 'warning'}
                            size="small"
                            sx={{ mr: 1 }}
                          />
                          {reading.confidence != null && (
                            <Chip 
                              label={`${(reading.confidence * 100).toFixed(0)}%`}
                              size="small"
                              color={reading.confidence > 0.7 ? 'success' : 'warning'}
                              variant="outlined"
                            />
                          )}
                        </Box>
                      </Box>
                      <Typography variant="caption" color="textSecondary">
                        Motor: {reading.motor_temp.toFixed(1)}°C, {reading.motor_vib.toFixed(2)}Hz | 
                        Pump: {reading.pump_temp.toFixed(1)}°C, {reading.pump_ultra.toFixed(1)}dB
                      </Typography>
                    </Box>
                  );
                })
              )}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
}
