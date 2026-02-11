import React from 'react';
import { Card, CardContent, Typography, Box, LinearProgress } from '@mui/material';

interface SensorCardProps {
  sensor: {
    sensor_id: string;
    name: string;
    status: string;
    value?: number;
  };
}

export default function SensorCard({ sensor }: SensorCardProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'success.main';
      case 'warning':
        return 'warning.main';
      case 'error':
        return 'error.main';
      default:
        return 'grey.500';
    }
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6">{sensor.name}</Typography>
          <Box
            sx={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              bgcolor: getStatusColor(sensor.status)
            }}
          />
        </Box>
        <Typography variant="body2" color="text.secondary">
          ID: {sensor.sensor_id}
        </Typography>
        {sensor.value && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="h4">{sensor.value.toFixed(2)}</Typography>
            <LinearProgress variant="determinate" value={sensor.value} sx={{ mt: 1 }} />
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
