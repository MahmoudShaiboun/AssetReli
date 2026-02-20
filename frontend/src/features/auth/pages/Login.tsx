import React, { useState } from 'react';
import {
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
  Link as MuiLink
} from '@mui/material';
import { useNavigate, Link } from 'react-router-dom';
import authService from '../../../api/auth';
import { useTenantContext } from '../../../contexts/TenantContext';

export default function Login() {
  const navigate = useNavigate();
  const { refreshFromToken } = useTenantContext();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await authService.login(email, password);
      refreshFromToken();
      navigate('/');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg || String(d)).join('; '));
      } else {
        setError('Login failed. Please check your credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper sx={{ p: 4 }}>
        <Typography variant="h4" gutterBottom align="center">
          Aastreli Login
        </Typography>
        <Typography variant="body2" color="textSecondary" align="center" gutterBottom>
          Industrial Anomaly Detection System
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mt: 2, mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSubmit} sx={{ mt: 3 }}>
          <TextField
            fullWidth
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            sx={{ mb: 2 }}
            autoFocus
          />
          <TextField
            fullWidth
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            sx={{ mb: 3 }}
          />
          <Button
            fullWidth
            type="submit"
            variant="contained"
            size="large"
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Login'}
          </Button>

          <Box sx={{ mt: 2, textAlign: 'center' }}>
            <Typography variant="body2">
              Don't have an account?{' '}
              <MuiLink component={Link} to="/register">
                Register here
              </MuiLink>
            </Typography>
          </Box>
        </Box>
      </Paper>
    </Container>
  );
}
