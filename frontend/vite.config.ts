/**
 * Vite (Fase 9.1): compilacion de la SPA y modo de desarrollo limitado a loopback.
 *
 * Modo desarrollo (`npm run dev`): Vite escucha solo en 127.0.0.1:5173 (o
 * `VITE_PUERTO`), sin CORS, y reenvia `/api/v1` y `/pasarela` a la pasarela
 * (`PASARELA_URL`, por defecto http://127.0.0.1:8020) sin cambiar `Host`. La
 * pasarela conserva todos sus controles: para aceptar este modo hay que anadir
 * de forma explicita `127.0.0.1:5173` a `PASARELA_HOSTS` y
 * `http://127.0.0.1:5173` a `PASARELA_ORIGENES`. La clave nunca pasa por Vite.
 *
 * Solo las variables `VITE_PUBLICO_*` llegarian al JavaScript compilado; la
 * interfaz no usa ninguna.
 */
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

function pasarelaLocal(texto: string): string {
  const url = new URL(texto);
  const local = ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
  if (url.protocol !== "http:" || !local || !url.port || url.username || url.password || url.search || url.hash
      || (url.pathname !== "/" && url.pathname !== "")) {
    throw new Error("PASARELA_URL debe ser http:// loopback con puerto, sin credenciales ni ruta");
  }
  return url.origin;
}

const pasarela = pasarelaLocal(process.env.PASARELA_URL ?? "http://127.0.0.1:8020");
const puerto = Number(process.env.VITE_PUERTO ?? "5173");
const reenvio = { target: pasarela, changeOrigin: false, xfwd: false, followRedirects: false };

export default defineConfig({
  plugins: [react()],
  envPrefix: "VITE_PUBLICO_",
  server: {
    host: "127.0.0.1",
    port: puerto,
    strictPort: true,
    cors: false,
    allowedHosts: [],
    proxy: { "/api/v1": reenvio, "/pasarela": reenvio },
  },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false, assetsInlineLimit: 0 },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/pruebas/preparacion.ts"],
  },
});
