import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendUrl = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
const frontendPort = parseInt(process.env.VITE_PORT ?? '3000')

export default defineConfig({
  plugins: [react()],
  server: {
    port: frontendPort,
    proxy: {
      '/api':    backendUrl,
      '/health': backendUrl,
    },
  },
})
