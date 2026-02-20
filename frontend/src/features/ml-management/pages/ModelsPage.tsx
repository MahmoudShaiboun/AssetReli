import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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

interface Model {
  id: string;
  model_name: string;
  model_type: string;
  framework: string;
  description: string;
  is_active: boolean;
}

export default function ModelsPage() {
  const { tenantVersion } = useTenantContext();
  const navigate = useNavigate();
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await apiClient.get('/ml/models');
        setModels(response.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to fetch models.');
      } finally {
        setLoading(false);
      }
    };
    fetchModels();
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
        ML Models
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
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Framework</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {models.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No models found.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              models.map((model) => (
                <TableRow
                  key={model.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/models/${model.id}`)}
                >
                  <TableCell>{model.model_name}</TableCell>
                  <TableCell>{model.model_type}</TableCell>
                  <TableCell>{model.framework}</TableCell>
                  <TableCell>{model.description}</TableCell>
                  <TableCell>
                    <Chip
                      label={model.is_active ? 'Active' : 'Inactive'}
                      color={model.is_active ? 'success' : 'default'}
                      size="small"
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
