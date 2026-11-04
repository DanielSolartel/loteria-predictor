-- Fase 10 (E10.4): rol de CAPTURA en la base FUENTE. PENDIENTE para el PC de Daniel: crear un rol en la base
-- que usa Fase 6 es una intervencion operativa que requiere su autorizacion (D10). En la demostracion y en CI se
-- aplica a la base DESECHABLE `loteria_prueba`.
--
-- Solo lectura (SELECT y transacciones de solo lectura por defecto) y `pg_read_all_stats` para VER las
-- transacciones de otros roles que ya escribieron (evidencia viva de escritores): sin ese permiso la captura se
-- rechaza. No puede escribir, tomar ni liberar los advisory de otros, ni cancelar sesiones.
\set ON_ERROR_STOP on
CREATE ROLE generaciones_captura LOGIN PASSWORD :'clave_captura' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    CONNECTION LIMIT 4;
GRANT pg_read_all_stats TO generaciones_captura;
GRANT CONNECT ON DATABASE :"base" TO generaciones_captura;
ALTER ROLE generaciones_captura SET default_transaction_read_only = on;
\connect :"base"
GRANT USAGE ON SCHEMA public TO generaciones_captura;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO generaciones_captura;
