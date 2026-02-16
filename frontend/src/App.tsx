import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Dashboard from './pages/Dashboard';
import Predictions from './pages/Predictions';
import Feedback from './pages/Feedback';
import Settings from './pages/Settings';
import RealtimeData from './pages/RealtimeData';
import FaultTypes from './pages/FaultTypes';
import Sensors from './pages/Sensors';
import Login from './pages/Login';
import Register from './pages/Register';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import authService from './services/auth';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          
          {/* Protected routes */}
          <Route path="/" element={
            <ProtectedRoute>
              <Layout><Dashboard /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/sensors" element={
            <ProtectedRoute>
              <Layout><Sensors /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/realtime" element={
            <ProtectedRoute>
              <Layout><RealtimeData /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/predictions" element={
            <ProtectedRoute>
              <Layout><Predictions /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/fault-types" element={
            <ProtectedRoute>
              <Layout><FaultTypes /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/feedback" element={
            <ProtectedRoute>
              <Layout><Feedback /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/settings" element={
            <ProtectedRoute>
              <Layout><Settings /></Layout>
            </ProtectedRoute>
          } />
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;
