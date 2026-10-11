import react from '@vitejs/plugin-react'
import { defineConfig, searchForWorkspaceRoot } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // src/live.ts reads ../engine/soils.json so the dashboard and the engine share
  // one soil table; let the dev server serve that folder too.
  server: { fs: { allow: [searchForWorkspaceRoot(process.cwd()), '../engine'] } },
})
