import React, { useState, useEffect } from 'react';
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
  Checkbox,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Box,
  Alert,
  Chip,
  Pagination,
  CircularProgress
} from '@mui/material';
import { submitFeedback } from '../services/api';
import axios from 'axios';

interface SensorReading {
  _id: string;
  sensor_id: string;
  timestamp: string;
  temperature?: number;
  vibration?: number;
  pressure?: number;
  humidity?: number;
  motor_data?: any;
  pump_data?: any;
  full_features?: number[];
  has_feedback: boolean;
  prediction?: string;
  confidence?: number;
  fault_label?: string;
  state?: string;
}

const feedbackTypes = [
  { value: 'normal', label: 'Normal (No Fault)' },
  { value: 'pump_bearing_cage_defect', label: 'Pump Bearing Cage Defect' },
  { value: 'hydraulic_pulsation_resonance', label: 'Hydraulic Pulsation Resonance' },
  { value: 'bearing_overgrease_churn', label: 'Bearing Overgrease Churn' },
  { value: 'check_valve_flutter_proxy', label: 'Check Valve Flutter Proxy' },
  { value: 'data_dropout', label: 'Data Dropout' },
  { value: 'loss_of_prime_dry_run_proxy', label: 'Loss of Prime Dry Run Proxy' },
  { value: 'impeller_damage', label: 'Impeller Damage' },
  { value: 'belt_slip_or_drive_issue', label: 'Belt Slip or Drive Issue' },
  { value: 'suction_strainer_plugging', label: 'Suction Strainer Plugging' },
  { value: 'bearing_fit_tight_preload', label: 'Bearing Fit Tight Preload' },
  { value: 'rotor_bar_crack_proxy', label: 'Rotor Bar Crack Proxy' },
  { value: 'internal_rub_proxy', label: 'Internal Rub Proxy' },
  { value: 'seal_flush_failure_proxy', label: 'Seal Flush Failure Proxy' },
  { value: 'phase_unbalance', label: 'Phase Unbalance' },
  { value: 'lube_contamination_water', label: 'Lube Contamination Water' },
  { value: 'stuck_sensor_flatline', label: 'Stuck Sensor Flatline' },
  { value: 'piping_strain', label: 'Piping Strain' },
  { value: 'sensor_drift_bias', label: 'Sensor Drift Bias' },
  { value: 'instrument_scaling_error', label: 'Instrument Scaling Error' },
  { value: 'fan_blade_damage', label: 'Fan Blade Damage' },
  { value: 'coupling_wear', label: 'Coupling Wear' },
  { value: 'discharge_restriction', label: 'Discharge Restriction' },
  { value: 'power_frequency_variation', label: 'Power Frequency Variation' },
  { value: 'wear_ring_clearance', label: 'Wear Ring Clearance' },
  { value: 'foundation_grout_degradation', label: 'Foundation Grout Degradation' },
  { value: 'shaft_bow_proxy', label: 'Shaft Bow Proxy' },
  { value: 'bearing_fit_loose_housing', label: 'Bearing Fit Loose Housing' },
  { value: 'loose_hub_keyway', label: 'Loose Hub Keyway' },
  { value: 'air_gas_ingress', label: 'Air Gas Ingress' },
  { value: 'cooling_failure', label: 'Cooling Failure' },
  { value: 'blower_aero_stall_surge_proxy', label: 'Blower Aero Stall Surge Proxy' },
  { value: 'electrical_fluting', label: 'Electrical Fluting' },
  { value: 'seal_face_distress_proxy', label: 'Seal Face Distress Proxy' }
];

export default function Feedback() {
  const [readings, setReadings] = useState<SensorReading[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [feedbackLabel, setFeedbackLabel] = useState('normal');
  const [notes, setNotes] = useState('');
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const limit = 50;

  useEffect(() => {
    fetchReadings();
  }, [page]);

  const fetchReadings = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`http://localhost:8008/sensor-readings`, {
        params: {
          skip: (page - 1) * limit,
          limit: limit
        }
      });
      setReadings(response.data.readings);
      setTotalPages(Math.ceil(response.data.total / limit));
      setLoading(false);
    } catch (err) {
      console.error('Error fetching readings:', err);
      setError('Failed to load sensor readings');
      setLoading(false);
    }
  };

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      const allIds = new Set(readings.map(r => r._id));
      setSelectedIds(allIds);
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectOne = (id: string, event?: React.MouseEvent) => {
    // Prevent event bubbling if called from checkbox
    if (event) {
      event.stopPropagation();
    }
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleOpenDialog = () => {
    if (selectedIds.size === 0) {
      setError('Please select at least one reading');
      return;
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setFeedbackLabel('normal');
    setNotes('');
  };

  const handleSubmitFeedback = async () => {
    try {
      setError(null);
      setSubmitting(true);
      const selectedReadings = readings.filter(r => selectedIds.has(r._id));
      
      if (selectedReadings.length === 0) {
        setError('No readings selected');
        setSubmitting(false);
        return;
      }

      const feedbackPromises = selectedReadings.map(async (reading) => {
        // Extract features - use full_features if available, otherwise construct from available data
        let features: number[] = [];
        
        if (reading.full_features && Array.isArray(reading.full_features) && reading.full_features.length > 0) {
          features = reading.full_features;
        } else {
          // Construct basic features array from available fields
          const motorTemp = reading.motor_data?.DE_temp ?? reading.temperature ?? 0;
          const motorVib = reading.vibration ?? 0;
          const pumpTemp = reading.pump_data?.DE_temp ?? reading.humidity ?? 0;
          const pumpUltra = reading.pump_data?.DE_ultra ?? reading.pressure ?? 0;
          
          // Create a basic feature array
          features = [motorTemp, motorVib, pumpTemp, pumpUltra];
        }

        // Call API with proper parameter structure
        // Backend expects query parameters for original_prediction, corrected_label, feedback_type
        // and features as a JSON body (list)
        const response = await axios.post(
          'http://localhost:8008/feedback',
          features, // Send features array as the body
          {
            params: {
              original_prediction: reading.prediction || 'unknown',
              corrected_label: feedbackLabel,
              feedback_type: 'correction',
              confidence: reading.confidence,
              notes: notes || '',
              sensor_id: reading.sensor_id,
              reading_id: reading._id,
              timestamp: reading.timestamp
            },
            headers: {
              'Content-Type': 'application/json'
            }
          }
        );
        
        return response.data;
      });

      await Promise.all(feedbackPromises);
      
      setSuccess(true);
      setSelectedIds(new Set());
      handleCloseDialog();
      
      // Refresh the data
      await fetchReadings();
      
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      console.error('Error submitting feedback:', err);
      
      // Handle different error response formats
      let errorMsg = 'Failed to submit feedback';
      
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        // Check if detail is an array of validation errors
        if (Array.isArray(detail)) {
          errorMsg = detail.map((e: any) => {
            if (typeof e === 'object' && e.msg) {
              return `${e.loc?.join('.') || 'Field'}: ${e.msg}`;
            }
            return JSON.stringify(e);
          }).join(', ');
        } else if (typeof detail === 'string') {
          errorMsg = detail;
        } else if (typeof detail === 'object') {
          errorMsg = detail.msg || JSON.stringify(detail);
        }
      } else if (err.message) {
        errorMsg = err.message;
      }
      
      setError(errorMsg);
    } finally {
      setSubmitting(false);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  const formatValue = (value: number | undefined | null) => {
    return value != null ? value.toFixed(2) : 'N/A';
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          📋 Sensor Data Feedback & Anomalies
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Review predictions and anomalies. Select readings to provide feedback for model improvement.
        </Typography>
      </Box>

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(false)}>
          Feedback submitted successfully! The model will be updated in the next training cycle.
        </Alert>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Chip 
            label={`${selectedIds.size} selected`} 
            color={selectedIds.size > 0 ? "primary" : "default"}
          />
          <Chip 
            label={`${readings.filter(r => r.prediction && r.prediction.toLowerCase() !== 'normal').length} anomalies`}
            color="warning"
          />
          <Chip 
            label={`${readings.filter(r => r.has_feedback === true).length} with feedback`}
            color="success"
          />
        </Box>
        <Button 
          variant="contained" 
          color="primary"
          onClick={handleOpenDialog}
          disabled={selectedIds.size === 0}
        >
          Submit Feedback for Selected
        </Button>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      indeterminate={selectedIds.size > 0 && selectedIds.size < readings.length}
                      checked={readings.length > 0 && selectedIds.size === readings.length}
                      onChange={handleSelectAll}
                    />
                  </TableCell>
                  <TableCell><strong>Sensor ID</strong></TableCell>
                  <TableCell><strong>Timestamp</strong></TableCell>
                  <TableCell><strong>Motor Temp</strong></TableCell>
                  <TableCell><strong>Motor Vib</strong></TableCell>
                  <TableCell><strong>Pump Temp</strong></TableCell>
                  <TableCell><strong>Pump Ultra</strong></TableCell>
                  <TableCell><strong>ML Prediction</strong></TableCell>
                  <TableCell><strong>Confidence</strong></TableCell>
                  <TableCell><strong>Feedback</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {readings.map((reading) => {
                  const isAnomaly = reading.prediction && reading.prediction.toLowerCase() !== 'normal';
                  const motorTemp = reading.motor_data?.DE_temp ?? reading.temperature ?? null;
                  const motorVib = reading.vibration ?? null;
                  const pumpTemp = reading.pump_data?.DE_temp ?? null;
                  const pumpUltra = reading.pump_data?.DE_ultra ?? null;

                  return (
                    <TableRow
                      key={reading._id}
                      hover
                      onClick={() => handleSelectOne(reading._id)}
                      selected={selectedIds.has(reading._id)}
                      sx={{ 
                        cursor: 'pointer',
                        bgcolor: isAnomaly ? 'warning.light' : 'inherit',
                        '&:hover': {
                          bgcolor: isAnomaly ? 'warning.main' : 'action.hover'
                        }
                      }}
                    >
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selectedIds.has(reading._id)}
                          onChange={(e) => {
                            e.stopPropagation();
                            handleSelectOne(reading._id);
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        {reading.sensor_id}
                        {isAnomaly && (
                          <Chip 
                            label="⚠️ ANOMALY" 
                            color="error" 
                            size="small" 
                            sx={{ ml: 1 }}
                          />
                        )}
                      </TableCell>
                      <TableCell>{formatTimestamp(reading.timestamp)}</TableCell>
                      <TableCell>{formatValue(motorTemp)}</TableCell>
                      <TableCell>{formatValue(motorVib)}</TableCell>
                      <TableCell>{formatValue(pumpTemp)}</TableCell>
                      <TableCell>{formatValue(pumpUltra)}</TableCell>
                      <TableCell>
                        {reading.prediction ? (
                          <Chip 
                            label={reading.prediction} 
                            size="small"
                            color={reading.prediction.toLowerCase() === 'normal' ? 'success' : 'error'}
                          />
                        ) : (
                          <Chip label="No prediction" size="small" variant="outlined" />
                        )}
                      </TableCell>
                      <TableCell>
                        {reading.confidence != null && !isNaN(reading.confidence) ? (
                          <Chip 
                            label={`${(reading.confidence * 100).toFixed(0)}%`}
                            size="small"
                            color={reading.confidence > 0.7 ? 'success' : 'warning'}
                          />
                        ) : (
                          'N/A'
                        )}
                      </TableCell>
                      <TableCell>
                        {reading.has_feedback ? (
                          <Chip label="✓ Given" size="small" color="success" />
                        ) : (
                          <Chip label="Pending" size="small" variant="outlined" />
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>

          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
            <Pagination 
              count={totalPages} 
              page={page} 
              onChange={(e, value) => setPage(value)}
              color="primary"
            />
          </Box>
        </>
      )}

      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Submit Feedback for {selectedIds.size} Reading(s)</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              select
              fullWidth
              label="Correct Label"
              value={feedbackLabel}
              onChange={(e) => setFeedbackLabel(e.target.value)}
              sx={{ mb: 3 }}
            >
              {feedbackTypes.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </TextField>

            <TextField
              fullWidth
              multiline
              rows={4}
              label="Notes (Optional)"
              placeholder="Add any additional information about this feedback..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog} disabled={submitting}>
            Cancel
          </Button>
          <Button 
            onClick={handleSubmitFeedback} 
            variant="contained" 
            color="primary"
            disabled={submitting}
          >
            {submitting ? 'Submitting...' : 'Submit Feedback'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
