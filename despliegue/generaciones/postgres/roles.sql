-- Fase 10 (E10.4): roles de las GENERACIONES en el PostgreSQL de CONSULTA (servidor; desechable en la demostracion).
-- Se ejecuta con un superusuario DESPUES de `despliegue/consulta-privada/postgres/roles.sql` (que crea
-- `consulta_lector`). La contrasena llega por la entrada estandar de psql (`\set clave_importador ...` antes de
-- este archivo), nunca por argumentos ni variables de entorno.
--
-- generaciones_importador: crea `prep_<id>_<intento>`, la migra y la carga como duena, concede CONNECT/SELECT al
--   lector, la renombra a `pub_<id>` y borra SOLO las bases cuya propiedad acredita (E104-IMP-01): duena = este
--   rol Y ajuste de base `loteria.importacion` (o `loteria.restauracion` en R-L) igual al de su raiz e intento.
--   Sin superusuario: CREATEDB y el permiso de fijar ESOS dos ajustes propios (PostgreSQL >= 15; sin el, un rol
--   no superusuario no puede guardar un ajuste personalizado en su base y la importacion se rechaza).
\set ON_ERROR_STOP on
CREATE ROLE generaciones_importador LOGIN PASSWORD :'clave_importador' NOSUPERUSER CREATEDB NOCREATEROLE
    NOREPLICATION CONNECTION LIMIT 8;
GRANT CONNECT ON DATABASE postgres TO generaciones_importador;
GRANT SET ON PARAMETER loteria.importacion, loteria.restauracion TO generaciones_importador;
