import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Paper,
  Box,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Alert,
  CircularProgress
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import apiClient from '../../../api/client';
import { useTenantContext } from '../../../contexts/TenantContext';

interface AlarmEvent {
  id: string;
  rule_name: string;
  severity: string;
  triggered_at: string;
  acknowledged: boolean;
  acknowledged_by?: string;
  message: string;
}

const SEVERITY_COLORS: Record<string, 'error' | 'warning' | 'info' | 'default'> = {
  critical: 'error',
  warning: 'warning',
  info: 'info',
};

export default function AlarmEventsPage() {
  const { tenantVersion } = useTenantContext();
  const [events, setEvents] = useState<AlarmEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);

  const fetchEvents = async () => {
    try {
      const { data } = await apiClient.get('/alerts/events');
      setEvents(Array.isArray(data) ? data : data.events || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load alarm events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [tenantVersion]);

  const handleAcknowledge = async (eventId: string) => {
    setAcknowledgingId(eventId);
    setError(null);
    try {
      await apiClient.patch(`/alerts/events/${eventId}`, { acknowledged: true });
      setSuccess('Event acknowledged successfully');
      setTimeout(() => setSuccess(null), 4000);
      await fetchEvents();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to acknowledge event');
    } finally {
      setAcknowledgingId(null);
    }
  };

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Alarm Events</Typography>
        <Button variant="outlined" onClick={() => { setLoading(true); fetchEvents(); }}>
          Refresh
        </Button>
      </Box>

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{success}</Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell><strong>Time</strong></TableCell>
              <TableCell><strong>Rule</strong></TableCell>
              <TableCell><strong>Severity</strong></TableCell>
              <TableCell><strong>Message</strong></TableCell>
              <TableCell><strong>Status</strong></TableCell>
              <TableCell><strong>Actions</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {events.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No alarm events recorded.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              events.map((event) => (
                <TableRow key={event.id} hover>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {formatTime(event.triggered_at)}
                  </TableCell>
                  <TableCell>{event.rule_name}</TableCell>
                  <TableCell>
                    <Chip
                      label={event.severity}
                      size="small"
                      color={SEVERITY_COLORS[event.severity] || 'default'}
                    />
                  </TableCell>
                  <TableCell sx={{ maxWidth: 300 }}>
                    <Typography variant="body2" noWrap title={event.message}>
                      {event.message}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={event.acknowledged ? 'Acknowledged' : 'Pending'}
                      size="small"
                      color={event.acknowledged ? 'success' : 'warning'}
                      variant={event.acknowledged ? 'filled' : 'outlined'}
                    />
                    {event.acknowledged && event.acknowledged_by && (
                      <Typography variant="caption" display="block" color="text.secondary">
                        by {event.acknowledged_by}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {!event.acknowledged && (
                      <Button
                        size="small"
                        variant="outlined"
                        color="success"
                        startIcon={<CheckCircleIcon />}
                        onClick={() => handleAcknowledge(event.id)}
                        disabled={acknowledgingId === event.id}
                      >
                        {acknowledgingId === event.id ? 'Acknowledging...' : 'Acknowledge'}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Container>
  );
}
