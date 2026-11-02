from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://loteria:loteria@localhost:5432/loteria_predictor"
    environment: str = "development"

    # Techo de seguridad de paginación para los conectores de scraping.
    # NO es un límite operativo -es una red de seguridad contra un
    # origen que por error nunca deje de paginar. Debe quedar
    # cómodamente por encima del historial real de cualquier juego
    # (MiLoto: ~58 páginas, Baloto Revancha: ~121, ColorLoto: ~21 al
    # momento de escribir esto). Configurable por si el histórico
    # crece mucho más de lo esperado.
    max_paginas_absoluto_conectores: int = 2000

    # Producto 1: carpeta de los pronosticos experimentales guardados
    # (un JSON canonico por artefacto, nunca sobrescrito). Relativa al
    # directorio desde el que se arranca la aplicacion (`backend/`).
    directorio_pronosticos_experimentales: str = "storage/pronosticos"

    # Producto 3: registro de ejecuciones de la operacion diaria y cerrojos
    # por juego, separados de los artefactos de pronostico.
    directorio_operacion: str = "storage/operacion"

    # Producto 4: laboratorio de modelos (informes de experimentos,
    # pronosticos del laboratorio, progreso y cerrojos), separado de los
    # almacenes de Productos 1-3.
    directorio_laboratorio_modelos: str = "storage/laboratorio"
    # Fase 3: tiempo maximo, en segundos, de cada trabajo del proceso trabajador
    # del laboratorio (comparacion de un juego, entrenamiento de un modelo
    # registrado o pronostico con un modelo cargado).
    tiempo_maximo_trabajador_laboratorio: int = 1800

    # Producto 5: modelo combinado, carteras y simulacion (comparaciones,
    # carteras, simulaciones, configuraciones, progreso y cerrojos), separado
    # de los almacenes de Productos 1-4. Tiempo maximo, en segundos, de cada
    # trabajo del proceso trabajador (por juego).
    directorio_carteras_modelos: str = "storage/carteras"
    tiempo_maximo_trabajador_carteras: int = 300

    # Producto 6: informes guardados del centro de resultados (fotografias
    # inmutables de una consulta), separados de los almacenes de Productos 1-5.
    directorio_resultados_modelos: str = "storage/resultados"

    # Fase 4: explicaciones inmutables de las predicciones (centro de
    # predicciones), separadas de los almacenes de Productos 1-6. La
    # prediccion en si es la cartera de Producto 5; aqui solo se guarda su
    # explicacion versionada y el registro de sus pasos.
    directorio_predicciones_modelos: str = "storage/predicciones"

    # Fase 6: control explícito, separado de los modelos elegidos. Construir la
    # aplicación no crea esta configuración ni activa el Programador de tareas.
    directorio_automatizacion: str = "storage/automatizacion"
    archivo_operacion_automatica: str = ""

    # Fase 7: progreso y cerrojos de las simulaciones. El RESULTADO no se
    # guarda aqui: su fuente canonica es la tabla `simulaciones`. Tiempo
    # maximo, en segundos, de cada simulacion en su proceso trabajador.
    directorio_simulaciones: str = "storage/simulaciones"
    tiempo_maximo_trabajador_simulaciones: int = 3600

    # Fase 8: API publica de solo lectura (`app.api.publica.aplicacion:app`),
    # separada de la aplicacion local. Sin claves predeterminadas: vacia o no
    # valida, la API rechaza toda consulta protegida. Formato:
    # `id:sha256:<64 hex>` separados por comas (huellas, nunca las claves).
    api_publica_claves: str = ""
    # Cubeta de fichas POR PROCESO: por clave valida y por direccion IP.
    api_publica_fichas_por_minuto: int = 60
    api_publica_fichas_por_minuto_ip: int = 120
    api_publica_max_clientes_ip: int = 1024
    # Origenes explicitos (coma); vacio = CORS deshabilitado. `*` no se admite.
    api_publica_cors_origenes: str = ""
    api_publica_documentacion: bool = True

    # Fase 10 (E10.1): consola local. Almacén privado de cuentas y sesiones (SQLite propio, fuera de Git y de
    # los datos publicables; no se crea al arrancar: lo crea `python -m scripts.consola_cuentas crear`).
    # Relativo a `backend/`. `consola_cookie_segura` solo con HTTPS real (cookies `Secure` y prefijo `__Host-`).
    consola_seguridad_directorio: str = "privado/consola"
    consola_cookie_segura: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
