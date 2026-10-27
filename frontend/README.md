# Frontend de consulta (Fase 9.1)

SPA React 19 + TypeScript + Vite que consulta la API pública `/api/v1` a través de la pasarela local (`backend/app/pasarela/`). No contiene claves ni lógica de negocio: presenta lo que informa la API. Diseño, decisiones, límites y verificación: [backend/docs/fase9_frontend.md](../backend/docs/fase9_frontend.md). Protocolo de Windows: [backend/docs/fase9_windows.md](../backend/docs/fase9_windows.md).

La entrega 9.3 v2 añade un botón «Consultar fiabilidad» en la predicción guardada. La carga automática nueva o recargada cuenta todas las peticiones, incluido el catálogo: 1 + 3 = 4 fichas (máximo autorizado 6); la fiabilidad cuesta 3 solo por acción explícita. Se muestra como evidencia de la cartera únicamente cuando corresponde su contexto de línea/perfil/versión registrada; en otro caso se informa la ausencia y se conserva la consulta general identificada como configuración actual. `hasta` filtra objetivos y no acredita disponibilidad temporal.

**Plan acordado de cinco partes.** 9.1 (frontend de consulta y pasarela) y 9.2 (métricas anteriores y horario por juego) están integradas. La 9.3 v2 cubre explicación guardada, clasificación de candidatos y fiabilidad observada; está validada en Linux y Windows con Brave y aprobada por la auditoría, con el cierre documental preparado y la integración, publicación manual y CI del nuevo PR pendientes. La 9.4 añadirá consultas de modelos, carteras y resultados guardados; la 9.5, exportación, impresión y revisión final de navegación, móvil y accesibilidad. La 9.4 y la 9.5 no se implementan en esta entrega. Administración y operación permanecen en HTMX; los gráficos nuevos quedan para después. La Fase 9 global continúa abierta.

**Validación 9.3 v2:** Daniel ejecutó en Windows 11/Python 3.14.6 las 415 pruebas API/pasarela y, con Node 24.15.0, 690 Vitest (incluidas las 25 regresiones de contexto), sin fallos, errores u omisiones. Brave: 30 visitas y 32 comprobaciones a 360/390/1280 px, seis controles HTTP y dos comprobaciones de cuota; contador genérico de cuota: cero visitas. El auditor revisó 16 capturas sin bloqueos visuales. Contrato, tipos, compilación y canario correctos; no se atribuyen estos resultados a Codex ni se suman a Linux. [Cierre y pendientes](../backend/docs/fase9_3_validacion_operador_2026-10-27.md).

## Requisitos

Node ≥ 22.12 (LTS 22 o 24) y npm. Comprobar con `node --version` antes de instalar nada.

## Órdenes

| Orden | Qué hace |
|---|---|
| `npm ci --no-audit --no-fund --ignore-scripts` | instalación reproducible desde `package-lock.json` |
| `npm run tipos:comprobar` | `src/api/esquema.d.ts` coincide con la generación desde `src/api/openapi.json` |
| `npm run typecheck` | TypeScript estricto |
| `npm test` | pruebas de componentes (Vitest + Testing Library, en StrictMode) |
| `npm run build` | compila en `dist/` (sin mapas de código ni recursos externos) |
| `npm run canario` | compila con un canario en el entorno y comprueba que no llega al bundle; busca envío de credenciales, almacenamiento y recursos de terceros |
| `npm run tipos` | regenera `src/api/esquema.d.ts` (tras exportar el OpenAPI con `python -m scripts.exportar_openapi_publica ../frontend/src/api/openapi.json` desde `backend/`) |
| `npm run dev` | Vite en `127.0.0.1:5173`, con reenvío a la pasarela (ver abajo) |

## Uso local

Desde `backend/`:

1. API pública: `uvicorn app.api.publica.aplicacion:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers` (con la huella de la clave en `API_PUBLICA_CLAVES`).
2. Pasarela: `uvicorn app.pasarela.aplicacion:app --host 127.0.0.1 --port 8020 --no-access-log --no-proxy-headers` (con la clave en `PASARELA_CLAVE_API` o en `backend/pasarela.privado.env`, fuera de Git).
3. Abrir `http://127.0.0.1:8020/`.

**Modo desarrollo:** `npm run dev` reenvía `/api/v1` y `/pasarela` a `PASARELA_URL` (por defecto `http://127.0.0.1:8020`) sin cambiar `Host`. La pasarela solo lo acepta si se añaden de forma explícita `127.0.0.1:5173` a `PASARELA_HOSTS` y `http://127.0.0.1:5173` a `PASARELA_ORIGENES`.

## Estructura

- `src/api/` — OpenAPI versionado y tipos generados, decodificadores de presentación (`presentacion.ts`), cliente de la pasarela (`cliente.ts`) y formato (`formatos.ts`).
- `src/usos/consulta.ts` — carga con cancelación; descarta respuestas antiguas.
- `src/componentes/`, `src/pantallas/` — marco, estados y errores, tablas y pantallas.
- `src/pruebas/` — respuestas SINTÉTICAS producidas por la API real (`python -m tests.generar_respuestas_fase9 ../frontend/src/pruebas/respuestas` desde `backend/`) y casos de formato de la consola HTMX. Al regenerarlas cambian también la fecha de consulta, los días de frescura, UUID, horas y latencias; la 9.3 solo incorporó las respuestas que cambian por su contrato (predicciones y fiabilidad) y `formatos.json`.
- `scripts/` — comprobación de tipos y canario. `e2e/recorrido.mjs` — recorrido de Chromium que lanza `python -m tests.recorrido_fase9` desde `backend/`.
