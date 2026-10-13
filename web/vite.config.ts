import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    // En desarrollo: uvicorn en :8000 (cd server && uvicorn app.main:create_app --factory --reload)
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: { charts: ['recharts'], react: ['react', 'react-dom', 'react-router-dom', '@tanstack/react-query'] },
      },
    },
  },
})
