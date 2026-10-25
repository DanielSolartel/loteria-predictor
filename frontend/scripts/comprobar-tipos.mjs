/**
 * Comprueba que `src/api/esquema.d.ts` es exactamente lo que genera
 * openapi-typescript (version fijada en package-lock.json) a partir del
 * OpenAPI versionado `src/api/openapi.json`. La deriva frente a la app publica
 * de la base la comprueba backend/tests/unit/pasarela/test_pasarela_contrato.py.
 */
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const temporal = mkdtempSync(join(tmpdir(), "f9-tipos-"));
try {
  const salida = join(temporal, "esquema.d.ts");
  execFileSync(process.execPath, [join(raiz, "node_modules", "openapi-typescript", "bin", "cli.js"), join(raiz, "src", "api", "openapi.json"), "-o", salida], { stdio: "pipe" });
  const normalizar = (texto) => texto.replace(/\r\n/g, "\n");
  const generado = normalizar(readFileSync(salida, "utf8"));
  const versionado = normalizar(readFileSync(join(raiz, "src", "api", "esquema.d.ts"), "utf8"));
  if (generado !== versionado) {
    console.error("src/api/esquema.d.ts no coincide con la generacion desde src/api/openapi.json: ejecuta `npm run tipos`");
    process.exit(1);
  }
  console.log("tipos: esquema.d.ts coincide con openapi.json");
} finally {
  rmSync(temporal, { recursive: true, force: true });
}
