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
  CircularProgress,
  Tooltip
} from '@mui/material';
import apiClient from '../../../api/client';
import { useTenantContext } from '../../../contexts/TenantContext';

interface NotificationEntry {
  id: string;
  channel: string;
  recipient: string;
  subject: string;
  sent_at: string;
  status: string;
  error_message?: string;
}

const CHANNEL_COLORS: Record<string, 'primary' | 'secondary' | 'info' | 'default'> = {
  email: 'primary',
  sms: 'secondary',
  webhook: 'info',
  slack: 'default',
};

const STATUS_COLORS: Record<string, 'success' | 'error' | 'warning' | 'default'> = {
  sent: 'success',
  failed: 'error',
  pending: 'warning',
};

export default function NotificationLogPage() {
  const { tenantVersion } = useTenantContext();
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNotifications = async () => {
    try {
      const { data } = await apiClient.get('/alerts/notifications');
      setNotifications(Array.isArray(data) ? data : data.notifications || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load notification log');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, [tenantVersion]);

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
        <Typography variant="h4">Notification Log</Typography>
        <Button variant="outlined" onClick={() => { setLoading(true); fetchNotifications(); }}>
          Refresh
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell><strong>Time</strong></TableCell>
              <TableCell><strong>Channel</strong></TableCell>
              <TableCell><strong>Recipient</strong></TableCell>
              <TableCell><strong>Subject</strong></TableCell>
              <TableCell><strong>Status</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {notifications.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No notifications sent yet.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              notifications.map((entry) => (
                <TableRow key={entry.id} hover>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {formatTime(entry.sent_at)}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={entry.channel}
                      size="small"
                      color={CHANNEL_COLORS[entry.channel] || 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {entry.recipient}
                    </Typography>
                  </TableCell>
                  <TableCell sx={{ maxWidth: 300 }}>
                    <Typography variant="body2" noWrap title={entry.subject}>
                      {entry.subject}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {entry.error_message ? (
                      <Tooltip title={entry.error_message} arrow>
                        <Chip
                          label={entry.status}
                          size="small"
                          color={STATUS_COLORS[entry.status] || 'default'}
                        />
                      </Tooltip>
                    ) : (
                      <Chip
                        label={entry.status}
                        size="small"
                        color={STATUS_COLORS[entry.status] || 'default'}
                      />
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
