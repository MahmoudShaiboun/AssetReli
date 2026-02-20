import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Paper,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  CircularProgress,
  Alert,
} from '@mui/material';
import apiClient from '../../../api/client';
import { useTenantContext } from '../../../contexts/TenantContext';

interface FeedbackStats {
  total_count: number;
  breakdown: Record<string, number>;
}

export default function RetrainPage() {
  const { tenantVersion } = useTenantContext();
  const [stats, setStats] = useState<FeedbackStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [asyncMode, setAsyncMode] = useState(true);
  const [retraining, setRetraining] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [retrainError, setRetrainError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await apiClient.get('/ml/feedback/stats');
        setStats(response.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to fetch feedback stats.');
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, [tenantVersion]);

  const handleRetrain = async () => {
    setRetraining(true);
    setSuccessMessage(null);
    setRetrainError(null);
    try {
      const response = await apiClient.post('/ml/retrain', {
        async_mode: asyncMode,
      });
      setSuccessMessage(
        response.data.message || 'Retraining triggered successfully.'
      );
    } catch (err: any) {
      setRetrainError(
        err.response?.data?.detail || 'Failed to trigger retraining.'
      );
    } finally {
      setRetraining(false);
    }
  };

  if (loading) {
    return (
      <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        Model Retraining
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {stats && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Feedback Statistics
          </Typography>
          <Typography variant="body1" sx={{ mb: 1 }}>
            <strong>Total Feedback:</strong> {stats.total_count}
          </Typography>
          {Object.keys(stats.breakdown).length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Breakdown by Type
              </Typography>
              {Object.entries(stats.breakdown).map(([type, count]) => (
                <Typography key={type} variant="body2" sx={{ ml: 1 }}>
                  {type}: {count}
                </Typography>
              ))}
            </Box>
          )}
        </Paper>
      )}

      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Trigger Retraining
        </Typography>

        <FormControlLabel
          control={
            <Checkbox
              checked={asyncMode}
              onChange={(e) => setAsyncMode(e.target.checked)}
            />
          }
          label="Use async mode"
          sx={{ mb: 2, display: 'block' }}
        />

        <Button
          variant="contained"
          color="primary"
          onClick={handleRetrain}
          disabled={retraining}
          startIcon={retraining ? <CircularProgress size={20} /> : undefined}
        >
          {retraining ? 'Triggering...' : 'Trigger Retrain'}
        </Button>

        {successMessage && (
          <Alert severity="success" sx={{ mt: 2 }}>
            {successMessage}
          </Alert>
        )}

        {retrainError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {retrainError}
          </Alert>
        )}
      </Paper>
    </Container>
  );
}
