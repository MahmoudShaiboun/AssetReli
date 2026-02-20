import React from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';

interface LoadingSkeletonProps {
  message?: string;
}

export default function LoadingSkeleton({ message }: LoadingSkeletonProps) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', p: 4 }}>
      <CircularProgress />
      {message && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          {message}
        </Typography>
      )}
    </Box>
  );
}
