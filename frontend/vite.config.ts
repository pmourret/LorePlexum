import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Le proxy `/api` est ce qui garde le développement en **same-origin**, comme la
 * production : Traefik y route `/api` vers le backend et le reste vers ce
 * frontend, sur le même host. Aucune configuration CORS n'est donc nécessaire
 * nulle part, ce qui compte d'autant plus qu'il n'y a pas d'authentification
 * applicative — l'accès est restreint au niveau réseau.
 */
const proxy = {
  '/api': {
    target: process.env.BACKEND_URL ?? 'http://127.0.0.1:8000',
    changeOrigin: true,
  },
}

export default defineConfig({
  plugins: [react()],
  // `preview` sert le bundle de production : même proxy, pour pouvoir vérifier
  // le build réel et pas seulement le serveur de développement.
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
