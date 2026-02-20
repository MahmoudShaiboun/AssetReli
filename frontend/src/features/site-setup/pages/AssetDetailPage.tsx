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
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Grid,
  Chip,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../../../api/client';
import { useTenantContext } from '../../../contexts/TenantContext';

interface Asset {
  id: string;
  asset_code: string;
  asset_name: string;
  site_id: string;
  asset_type?: string;
  manufacturer?: string;
  model_number?: string;
}

interface Site {
  id: string;
  site_code: string;
  site_name: string;
}

interface Sensor {
  id: string;
  sensor_code: string;
  sensor_name: string;
  sensor_type?: string;
  unit?: string;
  is_active?: boolean;
}

export default function AssetDetailPage() {
  const { tenantVersion } = useTenantContext();
  const { assetId } = useParams<{ assetId: string }>();
  const navigate = useNavigate();

  const [asset, setAsset] = useState<Asset | null>(null);
  const [site, setSite] = useState<Site | null>(null);
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch asset details
        const { data: assetData } = await apiClient.get(`/assets/${assetId}`);
        setAsset(assetData);

        // Fetch site info for display
        if (assetData.site_id) {
          try {
            const { data: siteData } = await apiClient.get(`/sites`);
            const sitesList: Site[] = Array.isArray(siteData) ? siteData : siteData.sites || [];
            const matchedSite = sitesList.find((s) => s.id === assetData.site_id);
            if (matchedSite) setSite(matchedSite);
          } catch {
            // Site lookup is non-critical
          }
        }

        // Fetch associated sensors
        const { data: sensorData } = await apiClient.get(`/sensors`, {
          params: { asset_id: assetId },
        });
        setSensors(Array.isArray(sensorData) ? sensorData : sensorData.sensors || []);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load asset details');
      } finally {
        setLoading(false);
      }
    };

    if (assetId) {
      fetchData();
    }
  }, [assetId, tenantVersion]);

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  if (error || !asset) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/assets')} sx={{ mb: 2 }}>
          Back to Assets
        </Button>
        <Alert severity="error">{error || 'Asset not found'}</Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/assets')} sx={{ mb: 2 }}>
        Back to Assets
      </Button>

      {/* Asset Info Card */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h5" gutterBottom>
            {asset.asset_name}
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="caption" color="text.secondary">Asset Code</Typography>
              <Typography variant="body1" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                {asset.asset_code}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="caption" color="text.secondary">Site</Typography>
              <Typography variant="body1">
                {site ? `${site.site_name} (${site.site_code})` : asset.site_id}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="caption" color="text.secondary">Asset Type</Typography>
              <Typography variant="body1">{asset.asset_type || '\u2014'}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="caption" color="text.secondary">Manufacturer</Typography>
              <Typography variant="body1">{asset.manufacturer || '\u2014'}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="caption" color="text.secondary">Model Number</Typography>
              <Typography variant="body1">{asset.model_number || '\u2014'}</Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Sensors Table */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Associated Sensors</Typography>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell><strong>Sensor Code</strong></TableCell>
              <TableCell><strong>Sensor Name</strong></TableCell>
              <TableCell><strong>Type</strong></TableCell>
              <TableCell><strong>Unit</strong></TableCell>
              <TableCell><strong>Status</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sensors.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No sensors associated with this asset.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              sensors.map((sensor) => (
                <TableRow key={sensor.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {sensor.sensor_code}
                    </Typography>
                  </TableCell>
                  <TableCell>{sensor.sensor_name}</TableCell>
                  <TableCell>{sensor.sensor_type || '\u2014'}</TableCell>
                  <TableCell>{sensor.unit || '\u2014'}</TableCell>
                  <TableCell>
                    <Chip
                      label={sensor.is_active !== false ? 'Active' : 'Inactive'}
                      size="small"
                      color={sensor.is_active !== false ? 'success' : 'default'}
                    />
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
