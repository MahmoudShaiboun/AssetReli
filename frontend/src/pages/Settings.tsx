import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Paper,
  Box,
  Switch,
  FormControlLabel,
  TextField,
  Button,
  Divider,
  Grid,
  Alert,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import axios from 'axios';
import { triggerRetrain } from '../services/api';
import authService from '../services/auth';

interface FaultAction {
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

export default function Settings() {
  const [settings, setSettings] = useState({
    autoRefresh: true,
    refreshInterval: 5,
    anomalyThreshold: 0.7,
    enableNotifications: true,
    faultActions: [] as FaultAction[]
  });

  const [newAction, setNewAction] = useState({
    type: 'email' as 'email' | 'webhook' | 'sms' | 'slack',
    config: ''
  });

  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Load settings from backend API
  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get('http://localhost:8000/settings', {
        headers: authService.getAuthHeader()
      });
      setSettings(response.data);
    } catch (err: any) {
      console.error('Failed to load settings:', err);
      if (err.response?.status === 401) {
        setError('Session expired. Please login again.');
      }
    }
  };

  const handleSaveSettings = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await axios.post('http://localhost:8000/settings', settings, {
        headers: authService.getAuthHeader()
      });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setLoading(false);
    }
  };

  const handleAddAction = () => {
    if (!newAction.config) {
      setError('Please enter configuration');
      return;
    }

    const action: FaultAction = {
      id: Date.now().toString(),
      type: newAction.type,
      enabled: true,
      config: {}
    };

    // Parse config based on type
    if (newAction.type === 'email') {
      action.config.email = newAction.config;
    } else if (newAction.type === 'webhook') {
      action.config.url = newAction.config;
    } else if (newAction.type === 'sms') {
      action.config.phone = newAction.config;
    } else if (newAction.type === 'slack') {
      action.config.channel = newAction.config;
    }

    setSettings({
      ...settings,
      faultActions: [...settings.faultActions, action]
    });

    setNewAction({ type: 'email', config: '' });
    setError(null);
  };

  const handleDeleteAction = (id: string) => {
    setSettings({
      ...settings,
      faultActions: settings.faultActions.filter(a => a.id !== id)
    });
  };

  const handleToggleAction = (id: string) => {
    setSettings({
      ...settings,
      faultActions: settings.faultActions.map(a =>
        a.id === id ? { ...a, enabled: !a.enabled } : a
      )
    });
  };

  const handleTestAction = async (action: FaultAction) => {
    try {
      // Test the action by sending a test notification
      await axios.post('http://localhost:8000/test-notification', {
        type: action.type,
        config: action.config,
        message: 'Test notification from Aastreli system'
      });
      alert('Test notification sent successfully!');
    } catch (err) {
      alert('Failed to send test notification');
    }
  };

  const handleRetrain = async () => {
    try {
      await triggerRetrain();
      alert('Model retraining initiated successfully!');
    } catch (error) {
      setError('Error initiating model retraining');
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        ⚙️ System Settings
      </Typography>

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(false)}>
          Settings saved successfully!
        </Alert>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* General Settings */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          General Settings
        </Typography>
        <Divider sx={{ mb: 2 }} />

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.autoRefresh}
                  onChange={(e) => setSettings({ ...settings, autoRefresh: e.target.checked })}
                />
              }
              label="Auto-refresh Dashboard"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              type="number"
              label="Refresh Interval (seconds)"
              value={settings.refreshInterval}
              onChange={(e) => setSettings({ ...settings, refreshInterval: parseInt(e.target.value) })}
              disabled={!settings.autoRefresh}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              type="number"
              label="Anomaly Confidence Threshold (0-1)"
              value={settings.anomalyThreshold}
              onChange={(e) => setSettings({ ...settings, anomalyThreshold: parseFloat(e.target.value) })}
              inputProps={{ min: 0, max: 1, step: 0.1 }}
              helperText="Predictions above this threshold are considered anomalies"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.enableNotifications}
                  onChange={(e) => setSettings({ ...settings, enableNotifications: e.target.checked })}
                />
              }
              label="Enable Fault Notifications"
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Fault Actions */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          🚨 Fault Detection Actions
        </Typography>
        <Typography variant="body2" color="textSecondary" gutterBottom>
          Configure actions to trigger when a fault is detected
        </Typography>
        <Divider sx={{ mb: 2 }} />

        {/* Add New Action */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Add New Action
          </Typography>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Action Type</InputLabel>
                <Select
                  value={newAction.type}
                  label="Action Type"
                  onChange={(e) => setNewAction({ ...newAction, type: e.target.value as any })}
                >
                  <MenuItem value="email">📧 Email</MenuItem>
                  <MenuItem value="webhook">🔗 Webhook (HTTP)</MenuItem>
                  <MenuItem value="sms">📱 SMS</MenuItem>
                  <MenuItem value="slack">💬 Slack</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={7}>
              <TextField
                fullWidth
                label={
                  newAction.type === 'email' ? 'Email Address' :
                  newAction.type === 'webhook' ? 'Webhook URL' :
                  newAction.type === 'sms' ? 'Phone Number' :
                  'Slack Channel'
                }
                value={newAction.config}
                onChange={(e) => setNewAction({ ...newAction, config: e.target.value })}
                placeholder={
                  newAction.type === 'email' ? 'alerts@example.com' :
                  newAction.type === 'webhook' ? 'https://api.example.com/webhook' :
                  newAction.type === 'sms' ? '+1234567890' :
                  '#alerts'
                }
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <Button
                fullWidth
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleAddAction}
              >
                Add
              </Button>
            </Grid>
          </Grid>
        </Box>

        {/* List of Actions */}
        <List>
          {settings.faultActions.length === 0 ? (
            <ListItem>
              <ListItemText
                primary="No actions configured"
                secondary="Add actions above to receive notifications when faults are detected"
              />
            </ListItem>
          ) : (
            settings.faultActions.map((action) => (
              <ListItem
                key={action.id}
                sx={{
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  mb: 1,
                  bgcolor: action.enabled ? 'background.paper' : 'action.disabledBackground'
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1 }}>
                  <Switch
                    checked={action.enabled}
                    onChange={() => handleToggleAction(action.id)}
                  />
                  <Box>
                    <Typography variant="body1">
                      <Chip
                        label={action.type.toUpperCase()}
                        size="small"
                        color="primary"
                        sx={{ mr: 1 }}
                      />
                      {action.config.email || action.config.url || action.config.phone || action.config.channel}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      {action.enabled ? 'Active' : 'Disabled'}
                    </Typography>
                  </Box>
                </Box>
                <ListItemSecondaryAction>
                  <Button
                    size="small"
                    onClick={() => handleTestAction(action)}
                    sx={{ mr: 1 }}
                  >
                    Test
                  </Button>
                  <IconButton
                    edge="end"
                    onClick={() => handleDeleteAction(action.id)}
                  >
                    <DeleteIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))
          )}
        </List>
      </Paper>

      {/* ML Model Settings */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          🤖 ML Model Configuration
        </Typography>
        <Divider sx={{ mb: 2 }} />

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Typography variant="body2" color="textSecondary">
              <strong>Current Model:</strong> XGBoost v1.0<br />
              <strong>Features:</strong> 336 sensor features<br />
              <strong>Fault Types:</strong> 34 industrial fault categories<br />
              <strong>Last Training:</strong> {new Date().toLocaleDateString()}
            </Typography>
          </Grid>
          <Grid item xs={12}>
            <Button variant="outlined" color="primary" onClick={handleRetrain}>
              Trigger Model Retraining
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* System Information */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          📊 System Information
        </Typography>
        <Divider sx={{ mb: 2 }} />
        <Typography variant="body2" color="textSecondary">
          <strong>Frontend Version:</strong> 1.0.0<br />
          <strong>Backend API:</strong> http://localhost:8000<br />
          <strong>ML Service:</strong> http://localhost:8001<br />
          <strong>MQTT Broker:</strong> mqtt://localhost:1883<br />
          <strong>MongoDB:</strong> mongodb://localhost:27017
        </Typography>
      </Paper>

      {/* Save Button */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
        <Button
          variant="outlined"
          onClick={() => window.location.reload()}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          color="primary"
          onClick={handleSaveSettings}
        >
          Save Settings
        </Button>
      </Box>
    </Container>
  );
}
