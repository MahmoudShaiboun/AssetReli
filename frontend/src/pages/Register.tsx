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
import authService from '../services/auth';

export default function Register() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
    fullName: ''
  });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters long');
      return;
    }

    setLoading(true);

    try {
      await authService.register(
        formData.email,
        formData.username,
        formData.password,
        formData.fullName || undefined
      );
      // Register now returns a token and auto-logs in
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <Container maxWidth="sm" sx={{ mt: 8 }}>
        <Paper sx={{ p: 4 }}>
          <Alert severity="success">
            Registration successful! Redirecting to login...
          </Alert>
        </Paper>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper sx={{ p: 4 }}>
        <Typography variant="h4" gutterBottom align="center">
          📝 Create Account
        </Typography>
        <Typography variant="body2" color="textSecondary" align="center" gutterBottom>
          Register for Aastreli System
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
            name="email"
            type="email"
            value={formData.email}
            onChange={handleChange}
            required
            sx={{ mb: 2 }}
            autoFocus
          />
          <TextField
            fullWidth
            label="Username"
            name="username"
            value={formData.username}
            onChange={handleChange}
            required
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="Full Name (optional)"
            name="fullName"
            value={formData.fullName}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="Password"
            name="password"
            type="password"
            value={formData.password}
            onChange={handleChange}
            required
            sx={{ mb: 2 }}
            helperText="At least 6 characters"
          />
          <TextField
            fullWidth
            label="Confirm Password"
            name="confirmPassword"
            type="password"
            value={formData.confirmPassword}
            onChange={handleChange}
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
            {loading ? 'Creating account...' : 'Register'}
          </Button>

          <Box sx={{ mt: 2, textAlign: 'center' }}>
            <Typography variant="body2">
              Already have an account?{' '}
              <MuiLink component={Link} to="/login">
                Login here
              </MuiLink>
            </Typography>
          </Box>
        </Box>
      </Paper>
    </Container>
  );
}
