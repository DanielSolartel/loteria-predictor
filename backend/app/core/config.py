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


@lru_cache
def get_settings() -> Settings:
    return Settings()
