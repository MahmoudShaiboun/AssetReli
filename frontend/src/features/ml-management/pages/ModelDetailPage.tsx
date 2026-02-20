import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  CircularProgress,
  Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
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

interface ModelVersion {
  id: string;
  version: string;
  stage: string;
  accuracy: number | null;
  f1_score: number | null;
  training_date: string;
}

const stageChipColor = (stage: string): 'success' | 'info' | 'default' => {
  switch (stage.toLowerCase()) {
    case 'production':
      return 'success';
    case 'staging':
      return 'info';
    default:
      return 'default';
  }
};

export default function ModelDetailPage() {
  const { tenantVersion } = useTenantContext();
  const { modelId } = useParams<{ modelId: string }>();
  const navigate = useNavigate();

  const [model, setModel] = useState<Model | null>(null);
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [modelRes, versionsRes] = await Promise.all([
          apiClient.get(`/ml/models/${modelId}`),
          apiClient.get(`/ml/models/${modelId}/versions`),
        ]);
        setModel(modelRes.data);
        setVersions(versionsRes.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to fetch model details.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [modelId, tenantVersion]);

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
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate('/models')}
        sx={{ mb: 2 }}
      >
        Back to Models
      </Button>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {model && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h5" gutterBottom>
            {model.model_name}
          </Typography>
          <Box display="flex" gap={2} flexWrap="wrap" mb={1}>
            <Typography variant="body2" color="text.secondary">
              <strong>Type:</strong> {model.model_type}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>Framework:</strong> {model.framework}
            </Typography>
            <Chip
              label={model.is_active ? 'Active' : 'Inactive'}
              color={model.is_active ? 'success' : 'default'}
              size="small"
            />
          </Box>
          {model.description && (
            <Typography variant="body1" sx={{ mt: 1 }}>
              {model.description}
            </Typography>
          )}
        </Paper>
      )}

      <Typography variant="h6" gutterBottom>
        Versions
      </Typography>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Version</TableCell>
              <TableCell>Stage</TableCell>
              <TableCell>Accuracy</TableCell>
              <TableCell>F1 Score</TableCell>
              <TableCell>Training Date</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {versions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No versions found.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              versions.map((v) => (
                <TableRow key={v.id}>
                  <TableCell>{v.version}</TableCell>
                  <TableCell>
                    <Chip
                      label={v.stage}
                      color={stageChipColor(v.stage)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {v.accuracy != null ? `${(v.accuracy * 100).toFixed(1)}%` : '-'}
                  </TableCell>
                  <TableCell>
                    {v.f1_score != null ? v.f1_score.toFixed(4) : '-'}
                  </TableCell>
                  <TableCell>
                    {new Date(v.training_date).toLocaleString()}
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
