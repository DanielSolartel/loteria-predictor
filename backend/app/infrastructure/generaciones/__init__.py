"""Fase 10 (E10.4): generaciones selladas, captura coherente, importacion, validacion y respaldos.

Modulos:
- `formato`: JSON canonico, huellas, rutas seguras y constantes del formato `generacion-e104/1`;
- `inventario`: matriz de datos (DAT-01): publicables, estado operativo, transitorios y secretos;
- `base_logica`: volcado logico de PostgreSQL desde una instantanea, huellas de contenido y de version de
  fila, huella del esquema y restauracion exacta;
- `archivos`: fotografia de los arboles observados, copia verificada y reservas huerfanas;
- `escritores`: evidencia viva de escritores (cerrojos, registros, advisory y transacciones con escritura);
- `coherencia`: coherencia cruzada por tipo de artefacto con los contratos existentes (F10-CAP-02);
- `firma`: Ed25519 del manifiesto (autenticidad);
- `captura`: el metodo de captura (D10, pendiente de aprobacion para datos reales) y el sellado;
- `verificacion`: integridad, autenticidad y compatibilidad de un paquete;
- `importacion`: preparacion aislada, validacion completa, aceptacion o rechazo seguro, activacion;
- `respaldo`: respaldo cifrado, verificacion, restauracion aislada (R-L) y retencion.

Ninguno de estos modulos pausa Fase 6, toma sus cerrojos ni modifica su estado o su tarea programada.
"""
