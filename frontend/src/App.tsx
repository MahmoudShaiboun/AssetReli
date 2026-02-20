import React, { Suspense, lazy, useMemo, useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { CacheProvider } from '@emotion/react';
import createCache from '@emotion/cache';
import rtlPlugin from 'stylis-plugin-rtl';
import { prefixer } from 'stylis';
import i18n from './i18n';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import ErrorBoundary from './components/ErrorBoundary';
import LoadingSkeleton from './components/LoadingSkeleton';
import { TenantProvider } from './contexts/TenantContext';
import TenantSelector from './components/TenantSelector';

// Auth (public)
const Login = lazy(() => import('./features/auth/pages/Login'));
const Register = lazy(() => import('./features/auth/pages/Register'));

// Dashboard
const DashboardPage = lazy(() => import('./features/dashboard/pages/DashboardPage'));

// Site Setup
const SensorsPage = lazy(() => import('./features/site-setup/pages/SensorsPage'));
const SitesPage = lazy(() => import('./features/site-setup/pages/SitesPage'));
const GatewaysPage = lazy(() => import('./features/site-setup/pages/GatewaysPage'));
const AssetsPage = lazy(() => import('./features/site-setup/pages/AssetsPage'));
const AssetDetailPage = lazy(() => import('./features/site-setup/pages/AssetDetailPage'));

// Predictions
const RealtimeDataPage = lazy(() => import('./features/predictions/pages/RealtimeDataPage'));
const PredictionsPage = lazy(() => import('./features/predictions/pages/PredictionsPage'));
const FaultTypesPage = lazy(() => import('./features/predictions/pages/FaultTypesPage'));
const FeedbackPage = lazy(() => import('./features/predictions/pages/FeedbackPage'));

// ML Management
const ModelsPage = lazy(() => import('./features/ml-management/pages/ModelsPage'));
const ModelDetailPage = lazy(() => import('./features/ml-management/pages/ModelDetailPage'));
const DeploymentsPage = lazy(() => import('./features/ml-management/pages/DeploymentsPage'));
const RetrainPage = lazy(() => import('./features/ml-management/pages/RetrainPage'));

// Alerts
const AlarmRulesPage = lazy(() => import('./features/alerts/pages/AlarmRulesPage'));
const AlarmEventsPage = lazy(() => import('./features/alerts/pages/AlarmEventsPage'));
const NotificationLogPage = lazy(() => import('./features/alerts/pages/NotificationLogPage'));
const WorkOrdersPage = lazy(() => import('./features/alerts/pages/WorkOrdersPage'));

// Administration
const TenantsPage = lazy(() => import('./features/admin/pages/TenantsPage'));
const UsersPage = lazy(() => import('./features/admin/pages/UsersPage'));

// Settings
const SettingsPage = lazy(() => import('./features/settings/pages/SettingsPage'));

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

// Emotion caches for LTR and RTL
const ltrCache = createCache({ key: 'mui' });
const rtlCache = createCache({ key: 'muirtl', stylisPlugins: [prefixer, rtlPlugin] });

function AppInner() {
  const [dir, setDir] = useState<'ltr' | 'rtl'>(i18n.language === 'ar' ? 'rtl' : 'ltr');

  useEffect(() => {
    const onLangChanged = (lng: string) => {
      const newDir = lng === 'ar' ? 'rtl' : 'ltr';
      setDir(newDir);
      document.documentElement.dir = newDir;
      document.documentElement.lang = lng;
    };
    // Set initial direction
    onLangChanged(i18n.language);
    i18n.on('languageChanged', onLangChanged);
    return () => { i18n.off('languageChanged', onLangChanged); };
  }, []);

  const theme = useMemo(
    () =>
      createTheme({
        direction: dir,
        palette: {
          mode: 'light',
          primary: { main: '#1976d2' },
          secondary: { main: '#dc004e' },
        },
      }),
    [dir],
  );

  return (
    <CacheProvider value={dir === 'rtl' ? rtlCache : ltrCache}>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <TenantProvider>
      <TenantSelector />
      <Router>
        <Suspense fallback={<LoadingSkeleton message="Loading..." />}>
          <Routes>
              {/* Public routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />

              {/* Dashboard */}
              <Route path="/" element={<ProtectedLayout><DashboardPage /></ProtectedLayout>} />

              {/* Site Setup */}
              <Route path="/sensors" element={<ProtectedLayout><SensorsPage /></ProtectedLayout>} />
              <Route path="/sites" element={<ProtectedLayout><SitesPage /></ProtectedLayout>} />
              <Route path="/gateways" element={<ProtectedLayout><GatewaysPage /></ProtectedLayout>} />
              <Route path="/assets" element={<ProtectedLayout><AssetsPage /></ProtectedLayout>} />
              <Route path="/assets/:assetId" element={<ProtectedLayout><AssetDetailPage /></ProtectedLayout>} />

              {/* Predictions */}
              <Route path="/realtime" element={<ProtectedLayout><RealtimeDataPage /></ProtectedLayout>} />
              <Route path="/predictions" element={<ProtectedLayout><PredictionsPage /></ProtectedLayout>} />
              <Route path="/fault-types" element={<ProtectedLayout><FaultTypesPage /></ProtectedLayout>} />
              <Route path="/feedback" element={<ProtectedLayout><FeedbackPage /></ProtectedLayout>} />

              {/* ML Management */}
              <Route path="/models" element={<ProtectedLayout><ModelsPage /></ProtectedLayout>} />
              <Route path="/models/:modelId" element={<ProtectedLayout><ModelDetailPage /></ProtectedLayout>} />
              <Route path="/deployments" element={<ProtectedLayout><DeploymentsPage /></ProtectedLayout>} />
              <Route path="/retrain" element={<ProtectedLayout><RetrainPage /></ProtectedLayout>} />

              {/* Alerts */}
              <Route path="/alarm-rules" element={<ProtectedLayout><AlarmRulesPage /></ProtectedLayout>} />
              <Route path="/alarm-events" element={<ProtectedLayout><AlarmEventsPage /></ProtectedLayout>} />
              <Route path="/notifications" element={<ProtectedLayout><NotificationLogPage /></ProtectedLayout>} />
              <Route path="/work-orders" element={<ProtectedLayout><WorkOrdersPage /></ProtectedLayout>} />

              {/* Administration */}
              <Route path="/tenants" element={
                <ProtectedRoute requiredRoles={["super_admin"]}>
                  <Layout><TenantsPage /></Layout>
                </ProtectedRoute>
              } />
              <Route path="/users" element={
                <ProtectedRoute requiredRoles={["admin", "super_admin"]}>
                  <Layout><UsersPage /></Layout>
                </ProtectedRoute>
              } />

              {/* Settings */}
              <Route path="/settings" element={<ProtectedLayout><SettingsPage /></ProtectedLayout>} />
            </Routes>
          </Suspense>
      </Router>
      </TenantProvider>
    </ThemeProvider>
    </CacheProvider>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <AppInner />
    </ErrorBoundary>
  );
}

export default App;
