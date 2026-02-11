import React, { useState, useEffect } from 'react';
import {
  AppBar,
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Container,
  IconButton,
  Menu,
  MenuItem,
  Avatar
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Analytics as PredictionsIcon,
  Feedback as FeedbackIcon,
  Settings as SettingsIcon,
  ShowChart as RealtimeIcon,
  BugReport as FaultIcon,
  AccountCircle
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import authService from '../services/auth';

const drawerWidth = 240;

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Real-time Data', icon: <RealtimeIcon />, path: '/realtime' },
  { text: 'Predictions', icon: <PredictionsIcon />, path: '/predictions' },
  { text: 'Fault Types', icon: <FaultIcon />, path: '/fault-types' },
  { text: 'Feedback', icon: <FeedbackIcon />, path: '/feedback' },
  { text: 'Settings', icon: <SettingsIcon />, path: '/settings' }
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
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
    navigate('/login');
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            🏭 Aastreli - Industrial Anomaly Detection
          </Typography>
          {user && (
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Typography variant="body2" sx={{ mr: 2 }}>
                {user.full_name || user.username}
              </Typography>
              <IconButton
                size="large"
                onClick={handleMenu}
                color="inherit"
              >
                <AccountCircle />
              </IconButton>
              <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleClose}
              >
                <MenuItem disabled>
                  <Typography variant="body2">{user.email}</Typography>
                </MenuItem>
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
          <List>
            {menuItems.map((item) => (
              <ListItem key={item.text} disablePadding>
                <ListItemButton
                  selected={location.pathname === item.path}
                  onClick={() => navigate(item.path)}
                >
                  <ListItemIcon>{item.icon}</ListItemIcon>
                  <ListItemText primary={item.text} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Box>
      </Drawer>
      
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}
