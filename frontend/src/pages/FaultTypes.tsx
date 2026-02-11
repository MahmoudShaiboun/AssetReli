import React from 'react';
import {
  Container,
  Typography,
  Paper,
  Grid,
  Box,
  Chip
} from '@mui/material';

const AVAILABLE_FAULTS = [
  'normal',
  'pump_bearing_cage_defect',
  'hydraulic_pulsation_resonance',
  'bearing_overgrease_churn',
  'check_valve_flutter_proxy',
  'data_dropout',
  'loss_of_prime_dry_run_proxy',
  'impeller_damage',
  'belt_slip_or_drive_issue',
  'suction_strainer_plugging',
  'bearing_fit_tight_preload',
  'rotor_bar_crack_proxy',
  'internal_rub_proxy',
  'seal_flush_failure_proxy',
  'phase_unbalance',
  'lube_contamination_water',
  'stuck_sensor_flatline',
  'piping_strain',
  'sensor_drift_bias',
  'instrument_scaling_error',
  'fan_blade_damage',
  'coupling_wear',
  'discharge_restriction',
  'power_frequency_variation',
  'wear_ring_clearance',
  'foundation_grout_degradation',
  'shaft_bow_proxy',
  'bearing_fit_loose_housing',
  'loose_hub_keyway',
  'air_gas_ingress',
  'cooling_failure',
  'blower_aero_stall_surge_proxy',
  'electrical_fluting',
  'seal_face_distress_proxy'
];

export default function FaultTypes() {
  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>
          ⚙️ Available Fault Types
        </Typography>
        <Typography variant="body1" color="textSecondary" paragraph>
          The ML model can detect {AVAILABLE_FAULTS.length} different fault types in industrial equipment:
        </Typography>

        <Box sx={{ mt: 3 }}>
          <Grid container spacing={2}>
            {AVAILABLE_FAULTS.map((fault, index) => (
              <Grid item xs={12} sm={6} md={4} lg={3} key={fault}>
                <Paper 
                  sx={{ 
                    p: 2, 
                    bgcolor: fault === 'normal' ? 'success.light' : 'background.paper',
                    border: 1,
                    borderColor: fault === 'normal' ? 'success.main' : 'grey.300'
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Chip 
                      label={index + 1} 
                      size="small" 
                      color={fault === 'normal' ? 'success' : 'default'}
                    />
                    <Typography variant="body2" sx={{ fontWeight: fault === 'normal' ? 'bold' : 'normal' }}>
                      {fault.replace(/_/g, ' ').toUpperCase()}
                    </Typography>
                  </Box>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </Box>

        <Box sx={{ mt: 4, p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
          <Typography variant="h6" gutterBottom>
            📊 Fault Categories
          </Typography>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="primary">
                Mechanical Faults:
              </Typography>
              <Typography variant="body2">
                • Bearing defects (cage, overgrease, fit issues)<br/>
                • Shaft problems (bow, rub, coupling wear)<br/>
                • Impeller damage, belt slip, loose components<br/>
                • Foundation and structural issues
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="primary">
                Hydraulic Faults:
              </Typography>
              <Typography variant="body2">
                • Pump issues (cavitation, dry run, prime loss)<br/>
                • Valve problems (flutter, restriction)<br/>
                • Pulsation, air ingress, seal failures<br/>
                • Wear ring clearance, strainer plugging
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="primary">
                Electrical Faults:
              </Typography>
              <Typography variant="body2">
                • Rotor bar cracks<br/>
                • Phase unbalance<br/>
                • Electrical fluting<br/>
                • Power frequency variations
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="primary">
                Sensor & Data Faults:
              </Typography>
              <Typography variant="body2">
                • Data dropout, sensor drift<br/>
                • Stuck sensors (flatline)<br/>
                • Instrument scaling errors<br/>
                • Calibration issues
              </Typography>
            </Grid>
          </Grid>
        </Box>
      </Paper>
    </Container>
  );
}
