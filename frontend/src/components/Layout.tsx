import React, { useState, useEffect } from 'react';
import {
  AppBar,
  Box,
  Chip,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Toolbar,
  Typography,
  IconButton,
  Menu,
  MenuItem,
  Divider,
  Select,
  SelectChangeEvent,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Analytics as PredictionsIcon,
  Feedback as FeedbackIcon,
  Settings as SettingsIcon,
  Sensors as SensorsIcon,
  ShowChart as RealtimeIcon,
  BugReport as FaultIcon,
  AccountCircle,
  Business as SitesIcon,
  Router as GatewaysIcon,
  PrecisionManufacturing as AssetsIcon,
  Psychology as ModelsIcon,
  Publish as DeployIcon,
  ModelTraining as RetrainIcon,
  NotificationsActive as AlarmIcon,
  EventNote as EventsIcon,
  MailOutline as NotifLogIcon,
  Engineering as WorkOrderIcon,
  Domain as TenantsIcon,
  People as UsersIcon,
  Language as LanguageIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import authService from '../api/auth';
import { useTenantContext } from '../contexts/TenantContext';

const drawerWidth = 240;

interface NavSection {
  label: string;
  items: { text: string; icon: React.ReactElement; path: string }[];
}

function getNavSections(isSuperAdmin: boolean, isAdmin: boolean): NavSection[] {
  const sections: NavSection[] = [
    {
      label: 'Dashboard',
      items: [
        { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
      ],
    },
    {
      label: 'Site Setup',
      items: [
        { text: 'Sites', icon: <SitesIcon />, path: '/sites' },
        { text: 'Gateways', icon: <GatewaysIcon />, path: '/gateways' },
        { text: 'Assets', icon: <AssetsIcon />, path: '/assets' },
        { text: 'Sensors', icon: <SensorsIcon />, path: '/sensors' },
      ],
    },
    {
      label: 'Predictions',
      items: [
        { text: 'Real-time Data', icon: <RealtimeIcon />, path: '/realtime' },
        { text: 'Predictions', icon: <PredictionsIcon />, path: '/predictions' },
        { text: 'Fault Types', icon: <FaultIcon />, path: '/fault-types' },
        { text: 'Feedback', icon: <FeedbackIcon />, path: '/feedback' },
      ],
    },
    {
      label: 'ML Management',
      items: [
        { text: 'Models', icon: <ModelsIcon />, path: '/models' },
        { text: 'Deployments', icon: <DeployIcon />, path: '/deployments' },
        { text: 'Retrain', icon: <RetrainIcon />, path: '/retrain' },
      ],
    },
    {
      label: 'Alerts',
      items: [
        { text: 'Alarm Rules', icon: <AlarmIcon />, path: '/alarm-rules' },
        { text: 'Alarm Events', icon: <EventsIcon />, path: '/alarm-events' },
        { text: 'Notification Log', icon: <NotifLogIcon />, path: '/notifications' },
        { text: 'Work Orders', icon: <WorkOrderIcon />, path: '/work-orders' },
      ],
    },
  ];

  if (isSuperAdmin) {
    sections.push({
      label: 'Administration',
      items: [
        { text: 'Tenants', icon: <TenantsIcon />, path: '/tenants' },
        { text: 'Users', icon: <UsersIcon />, path: '/users' },
      ],
    });
  } else if (isAdmin) {
    sections.push({
      label: 'Administration',
      items: [
        { text: 'Users', icon: <UsersIcon />, path: '/users' },
      ],
    });
  }

  sections.push({
    label: 'Settings',
    items: [
      { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
    ],
  });

  return sections;
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { i18n } = useTranslation();
  const { tenantId, tenants, isSuperAdmin, isAdmin, switchTenant, refreshFromToken } = useTenantContext();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [langAnchorEl, setLangAnchorEl] = useState<null | HTMLElement>(null);
  const [user, setUser] = useState(authService.getCurrentUser());

  useEffect(() => {
    setUser(authService.getCurrentUser());
  }, []);

  const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    authService.logout();
    refreshFromToken();
    navigate('/login');
  };

  const navSections = getNavSections(isSuperAdmin, isAdmin);
  const supportedLocales = (process.env.REACT_APP_SUPPORTED_LOCALES || 'en')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const localeLabels: Record<string, string> = { en: 'English', ar: 'العربية' };

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            Aastreli - Industrial Anomaly Detection
          </Typography>

          {/* Platform badge for super_admin */}
          {isSuperAdmin && (
            <Chip
              label="Platform"
              size="small"
              color="warning"
              sx={{ mr: 2, color: 'white', fontWeight: 600 }}
            />
          )}

          {/* Tenant switcher (super_admin only) */}
          {isSuperAdmin && tenants.length > 0 && (
            <Select
              size="small"
              value={tenantId || ''}
              displayEmpty
              onChange={(e: SelectChangeEvent) => switchTenant(e.target.value)}
              sx={{
                color: 'inherit',
                mr: 2,
                '& .MuiSelect-icon': { color: 'inherit' },
                '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.3)' },
                minWidth: 150,
                height: 36,
              }}
            >
              <MenuItem value="" disabled>
                Select Tenant...
              </MenuItem>
              {tenants.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.tenant_name || t.tenant_code}
                </MenuItem>
              ))}
            </Select>
          )}

          {/* Language switcher */}
          <IconButton
            size="large"
            color="inherit"
            onClick={(e) => setLangAnchorEl(e.currentTarget)}
            sx={{ mr: 1 }}
          >
            <LanguageIcon />
          </IconButton>
          <Menu anchorEl={langAnchorEl} open={Boolean(langAnchorEl)} onClose={() => setLangAnchorEl(null)}>
            {supportedLocales.map((loc) => (
              <MenuItem
                key={loc}
                selected={i18n.language === loc}
                onClick={() => { i18n.changeLanguage(loc); setLangAnchorEl(null); }}
              >
                {localeLabels[loc] || loc}
              </MenuItem>
            ))}
          </Menu>

          {user && (
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Typography variant="body2" sx={{ mr: 2 }}>
                {user.full_name || user.username}
              </Typography>
              <IconButton size="large" onClick={handleMenu} color="inherit">
                <AccountCircle />
              </IconButton>
              <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleClose}>
                <MenuItem disabled>
                  <Typography variant="body2">{user.email}</Typography>
                </MenuItem>
                {isSuperAdmin && (
                  <MenuItem disabled>
                    <Chip label="Super Admin" size="small" color="warning" />
                  </MenuItem>
                )}
                <MenuItem onClick={handleLogout}>Logout</MenuItem>
              </Menu>
            </Box>
          )}
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: drawerWidth, boxSizing: 'border-box' },
        }}
      >
        <Toolbar />
        <Box sx={{ overflow: 'auto' }}>
          {navSections.map((section, sectionIdx) => (
            <React.Fragment key={section.label}>
              <List
                subheader={
                  <ListSubheader component="div" sx={{ lineHeight: '36px', mt: sectionIdx > 0 ? 1 : 0 }}>
                    {section.label}
                  </ListSubheader>
                }
              >
                {section.items.map((item) => (
                  <ListItem key={item.text} disablePadding>
                    <ListItemButton
                      selected={location.pathname === item.path}
                      onClick={() => navigate(item.path)}
                      sx={{ py: 0.5 }}
                    >
                      <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
                      <ListItemText primary={item.text} primaryTypographyProps={{ variant: 'body2' }} />
                    </ListItemButton>
                  </ListItem>
                ))}
              </List>
              {sectionIdx < navSections.length - 1 && <Divider />}
            </React.Fragment>
          ))}
        </Box>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}
