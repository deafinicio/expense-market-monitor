import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins:[react()],
  base:'/expense-market-monitor/',
  build:{outDir:'docs',emptyOutDir:false,rollupOptions:{input:'index.html'}},
})
