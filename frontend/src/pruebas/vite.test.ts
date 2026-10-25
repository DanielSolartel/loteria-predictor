// @vitest-environment node
/** Modo desarrollo de Vite: solo loopback, sin CORS y un destino de pasarela validado. */
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function configuracion() {
  vi.resetModules();
  return (await import("../../vite.config")).default as {
    server: { host: string; port: number; strictPort: boolean; cors: boolean; allowedHosts: string[]; proxy: Record<string, Record<string, unknown>> };
    envPrefix: string;
    build: { sourcemap: boolean };
  };
}

describe("vite.config.ts", () => {
  it("escucha solo en 127.0.0.1, sin CORS y reenvia a la pasarela sin cambiar Host", async () => {
    const c = await configuracion();
    expect(c.server).toMatchObject({ host: "127.0.0.1", port: 5173, strictPort: true, cors: false, allowedHosts: [] });
    for (const ruta of ["/api/v1", "/pasarela"]) {
      expect(c.server.proxy[ruta]).toEqual({ target: "http://127.0.0.1:8020", changeOrigin: false, xfwd: false, followRedirects: false });
    }
    expect(Object.keys(c.server.proxy).sort()).toEqual(["/api/v1", "/pasarela"]);
    expect(c.envPrefix).toBe("VITE_PUBLICO_");
    expect(c.build.sourcemap).toBe(false);
  });

  it.each(["http://ajeno.example:8020", "https://127.0.0.1:8020", "http://127.0.0.1", "http://u:p@127.0.0.1:8020", "http://127.0.0.1:8020/api"])(
    "rechaza PASARELA_URL=%s",
    async (valor) => {
      vi.stubEnv("PASARELA_URL", valor);
      await expect(configuracion()).rejects.toThrow("PASARELA_URL debe ser http:// loopback");
    },
  );

  it("VITE_PUERTO cambia el puerto y sigue en loopback", async () => {
    vi.stubEnv("VITE_PUERTO", "5199");
    const c = await configuracion();
    expect(c.server.port).toBe(5199);
    expect(c.server.host).toBe("127.0.0.1");
  });
});
