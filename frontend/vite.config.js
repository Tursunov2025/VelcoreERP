import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_DEV_API_PROXY_TARGET?.trim()
  return ({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: proxyTarget ? {
      '/api-local': {
        target: proxyTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-local/, ''),
      },
    } : undefined,
  },
  preview: {
    host: true,
    port: 5173,
    // Cloudflare quick tunnel sends *.trycloudflare.com as Host
    allowedHosts: true,
  },
  build: {
    sourcemap: false,
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          pdf: ['jspdf', 'qrcode'],
          charts: ['recharts'],
        },
      },
    },
  },
  })
})
