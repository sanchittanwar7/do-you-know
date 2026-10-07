import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies API + OAuth to the Flask backend on :5001.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5001',
      '/img': 'http://localhost:5001',
      '/login': 'http://localhost:5001',
      '/callback': 'http://localhost:5001',
    },
  },
})
