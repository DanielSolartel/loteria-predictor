-- Fase 10 (E10.2): roles de la base de CONSULTA (desechable en la demostracion; en el servidor, E10.4/E10.5).
-- Se ejecuta con un superusuario ANTES de migrar. Las contrasenas llegan por la entrada estandar de psql
-- (`\set clave_propietario ...` y `\set clave_lector ...` antes de este archivo), nunca por argumentos ni
-- variables de entorno. `base` es el nombre de la base.
--
-- consulta_propietario: dueno del esquema y de las tablas (migraciones e importacion de la generacion).
-- consulta_lector: rol de la API privada. Solo CONNECT, USAGE y SELECT; transacciones de solo lectura por
--   defecto y limites propios de tiempo (ademas de los que fija la API en cada conexion).
\set ON_ERROR_STOP on
CREATE ROLE consulta_propietario LOGIN PASSWORD :'clave_propietario' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE consulta_lector LOGIN PASSWORD :'clave_lector' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    NOINHERIT CONNECTION LIMIT 16;
ALTER DATABASE :"base" OWNER TO consulta_propietario;
REVOKE ALL ON DATABASE :"base" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"base" TO consulta_propietario, consulta_lector;
ALTER ROLE consulta_lector SET default_transaction_read_only = on;
ALTER ROLE consulta_lector SET statement_timeout = '2s';
ALTER ROLE consulta_lector SET idle_in_transaction_session_timeout = '5s';
\connect :"base"
ALTER SCHEMA public OWNER TO consulta_propietario;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO consulta_lector;
ALTER DEFAULT PRIVILEGES FOR ROLE consulta_propietario IN SCHEMA public GRANT SELECT ON TABLES TO consulta_lector;
