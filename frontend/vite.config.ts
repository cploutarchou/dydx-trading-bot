import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_API_URL || 'http://localhost:8888',
          changeOrigin: true,
        },
      },
    },
    build: {
      chunkSizeWarningLimit: 700,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.indexOf('node_modules') === -1) return;

            const modulePath = id.split('node_modules/')[1] || '';
            const pathParts = modulePath.split('/');
            const firstPart = pathParts[0] || '';
            const packageName =
              firstPart.charAt(0) === '@' ? `${pathParts[0]}-${pathParts[1]}` : pathParts[0];

            if (id.indexOf('react-router') !== -1 || id.indexOf('@remix-run') !== -1) {
              return 'router-vendor';
            }

            if (id.indexOf('react-dom') !== -1 || id.indexOf('/react/') !== -1) {
              return 'react-core';
            }

            if (id.indexOf('echarts') !== -1 || id.indexOf('d3') !== -1) {
              return 'charts-vendor';
            }

            if (
              id.indexOf('@mui') !== -1 ||
              id.indexOf('@emotion') !== -1 ||
              id.indexOf('lucide-react') !== -1
            ) {
              return 'ui-vendor';
            }

            if (
              id.indexOf('axios') !== -1 ||
              id.indexOf('dayjs') !== -1 ||
              id.indexOf('lodash') !== -1
            ) {
              return 'utils-vendor';
            }

            if (id.indexOf('cookie') !== -1 || id.indexOf('set-cookie-parser') !== -1) {
              return 'utils-vendor';
            }

            const safePackage = (packageName || 'misc')
              .replace(/^@/, '')
              .replace(/[^a-zA-Z0-9_-]/g, '-');

            return `vendor-${safePackage}`;
          },
        },
      },
    },
  };
});
