import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // El puerto de Flask y el del propio Vite viven en el .env de la raíz del
  // proyecto (una sola fuente de verdad para backend y frontend), no en
  // frontend/.env. El tercer argumento '' carga TODAS las variables (no solo
  // las prefijadas VITE_): este archivo corre en Node, nunca llega al navegador.
  const env = loadEnv(mode, projectRoot, '')
  const flaskPort = env.FLASK_PORT || '5050'
  const vitePort = Number(env.VITE_PORT) || 5173
  // Vite valida el header Host de cada request contra una lista blanca (protección
  // contra DNS rebinding) — localhost/127.0.0.1/IPs pasan solo, pero un hostname de
  // DNS interno (ej. "my-pc.lan.example.com") hay que agregarlo a mano.
  const allowedHosts = env.VITE_ALLOWED_HOSTS
    ? env.VITE_ALLOWED_HOSTS.split(',').map((h) => h.trim()).filter(Boolean)
    : undefined

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: true,
      port: vitePort,
      allowedHosts,
      proxy: {
        '/api': {
          target: `http://localhost:${flaskPort}`,
          changeOrigin: true,
          // Sin esto, Flask solo ve el host "disfrazado" por changeOrigin
          // (siempre localhost:<FLASK_PORT>) y nunca el host real del navegador
          // (LAN, hostname interno) — rompe el login de Google, que necesita
          // saber a qué host volver. Ver _external_base_url en webapp/auth.py.
          xfwd: true,
        },
      },
    },
  }
})
