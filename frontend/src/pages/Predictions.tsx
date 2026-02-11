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
  Chip,
  CircularProgress,
  Box
} from '@mui/material';
import axios from 'axios';

interface SensorReading {
  _id: string;
  sensor_id: string;
  timestamp: string;
  prediction?: string;
  confidence?: number;
  motor_data?: any;
  pump_data?: any;
}

export default function Predictions() {
  const [predictions, setPredictions] = useState<SensorReading[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPredictions = async () => {
      try {
        const response = await axios.get('http://localhost:8000/sensor-readings', {
          params: { skip: 0, limit: 100 }
        });
        setPredictions(response.data.readings.filter((r: SensorReading) => r.prediction));
        setLoading(false);
      } catch (error) {
        console.error('Error fetching predictions:', error);
        setLoading(false);
      }
    };
    fetchPredictions();
    const interval = setInterval(fetchPredictions, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        🔮 ML Prediction History
      </Typography>
      <Typography variant="body2" color="textSecondary" gutterBottom>
        All sensor readings with ML predictions (Total: {predictions.length})
      </Typography>
      <TableContainer component={Paper} sx={{ mt: 3 }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell><strong>Timestamp (UTC)</strong></TableCell>
              <TableCell><strong>Sensor ID</strong></TableCell>
              <TableCell><strong>Prediction</strong></TableCell>
              <TableCell><strong>Confidence</strong></TableCell>
              <TableCell><strong>Motor Temp</strong></TableCell>
              <TableCell><strong>Pump Temp</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {predictions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography variant="body2" color="textSecondary">
                    No predictions yet. Waiting for sensor data...
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              predictions.map((pred: SensorReading) => (
                <TableRow 
                  key={pred._id}
                  sx={{ 
                    bgcolor: pred.prediction?.toLowerCase() !== 'normal' ? 'warning.light' : 'inherit' 
                  }}
                >
                  <TableCell>{new Date(pred.timestamp + 'Z').toLocaleString()}</TableCell>
                  <TableCell>{pred.sensor_id}</TableCell>
                  <TableCell>
                    <Chip
                      label={pred.prediction || 'Unknown'}
                      color={pred.prediction?.toLowerCase() === 'normal' ? 'success' : 'error'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {pred.confidence != null ? (
                      <Chip
                        label={`${(pred.confidence * 100).toFixed(1)}%`}
                        color={pred.confidence > 0.7 ? 'success' : 'warning'}
                        size="small"
                        variant="outlined"
                      />
                    ) : (
                      'N/A'
                    )}
                  </TableCell>
                  <TableCell>{pred.motor_data?.DE_temp?.toFixed(1) || 'N/A'}°C</TableCell>
                  <TableCell>{pred.pump_data?.DE_temp?.toFixed(1) || 'N/A'}°C</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Container>
  );
}
