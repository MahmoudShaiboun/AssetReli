import React from 'react';
import { Card, CardContent, Typography, Chip, Box } from '@mui/material';

interface PredictionCardProps {
  prediction: any;
}

export default function PredictionCard({ prediction }: PredictionCardProps) {
  const getConfidenceColor = (confidence: number) => {
    if (confidence > 0.8) return 'success';
    if (confidence > 0.6) return 'warning';
    return 'error';
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">
            {prediction.prediction}
          </Typography>
          <Chip
            label={`${(prediction.confidence * 100).toFixed(1)}%`}
            color={getConfidenceColor(prediction.confidence)}
            size="small"
          />
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {new Date(prediction.timestamp).toLocaleString()}
        </Typography>
      </CardContent>
    </Card>
  );
}
