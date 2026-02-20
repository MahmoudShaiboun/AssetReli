import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Paper,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  CircularProgress,
  Alert,
} from '@mui/material';
import apiClient from '../../../api/client';
import { useTenantContext } from '../../../contexts/TenantContext';

interface Deployment {
  id: string;
  model_name: string;
  version_label: string;
  is_production: boolean;
  deployed_at: string;
  deployed_by: string;
}

export default function DeploymentsPage() {
  const { tenantVersion } = useTenantContext();
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDeployments = async () => {
      try {
        const response = await apiClient.get('/ml/deployments');
        setDeployments(response.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to fetch deployments.');
      } finally {
        setLoading(false);
      }
    };
    fetchDeployments();
  }, [tenantVersion]);

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        Model Deployments
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Model Name</TableCell>
              <TableCell>Version</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Deployed At</TableCell>
              <TableCell>Deployed By</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {deployments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No deployments found.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              deployments.map((dep) => (
                <TableRow key={dep.id}>
                  <TableCell>{dep.model_name}</TableCell>
                  <TableCell>{dep.version_label}</TableCell>
                  <TableCell>
                    <Chip
                      label={dep.is_production ? 'Production' : 'Non-Production'}
                      color={dep.is_production ? 'success' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {new Date(dep.deployed_at).toLocaleString()}
                  </TableCell>
                  <TableCell>{dep.deployed_by}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Container>
  );
}
