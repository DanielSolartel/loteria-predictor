"""
Modelos SQLAlchemy — mapeo 1:1 del modelo ER revisado y aprobado.

Convención: estos modelos ORM son estrictamente de infraestructura.
El dominio (app.domain.entities) NUNCA importa de aquí, y estos
modelos nunca contienen lógica de negocio -solo mapeo de columnas y
relaciones. La traducción entre unos y otros vive en los
repositorios concretos (infrastructure/repositories).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class JuegoORM(Base):
    __tablename__ = "juegos"

    id: Mapped[uuid.UUID] = _uuid_pk()
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    rango_min: Mapped[int] = mapped_column(Integer, nullable=False)
    rango_max: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad_numeros: Mapped[int] = mapped_column(Integer, nullable=False)
    tiene_superbalota: Mapped[bool] = mapped_column(Boolean, default=False)
    superbalota_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    superbalota_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tiene_color: Mapped[bool] = mapped_column(Boolean, default=False)
    permite_repeticion: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    sorteos: Mapped[list["SorteoORM"]] = relationship(back_populates="juego")
    colores: Mapped[list["ColorORM"]] = relationship(back_populates="juego")


class SorteoORM(Base):
    __tablename__ = "sorteos"
    __table_args__ = (
        UniqueConstraint("juego_id", "numero_sorteo", name="uq_sorteo_juego_numero"),
        Index("ix_sorteos_juego_fecha", "juego_id", "fecha"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    juego_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("juegos.id"), nullable=False, index=True)
    numero_sorteo: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    dia_semana: Mapped[str] = mapped_column(String(15), nullable=False)
    fuente: Mapped[str | None] = mapped_column(String(100), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    juego: Mapped["JuegoORM"] = relationship(back_populates="sorteos")
    numeros: Mapped[list["SorteoNumeroORM"]] = relationship(
        back_populates="sorteo", cascade="all, delete-orphan"
    )
    superbalota: Mapped["SorteoSuperbalotaORM | None"] = relationship(
        back_populates="sorteo", cascade="all, delete-orphan", uselist=False
    )
    colores_numeros: Mapped[list["SorteoColorNumeroORM"]] = relationship(
        back_populates="sorteo", cascade="all, delete-orphan"
    )


class SorteoNumeroORM(Base):
    """Un número sorteado. Tabla normalizada (no INTEGER[]) para que
    consultas de frecuencia/correlación por número individual se
    indexen y escalen bien a millones de filas."""

    __tablename__ = "sorteo_numeros"
    __table_args__ = (UniqueConstraint("sorteo_id", "posicion", name="uq_sorteo_numero_posicion"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    sorteo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sorteos.id"), nullable=False, index=True)
    numero: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    posicion: Mapped[int] = mapped_column(Integer, nullable=False)

    sorteo: Mapped["SorteoORM"] = relationship(back_populates="numeros")


class SorteoSuperbalotaORM(Base):
    __tablename__ = "sorteo_superbalota"

    id: Mapped[uuid.UUID] = _uuid_pk()
    sorteo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sorteos.id"), nullable=False, unique=True
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    sorteo: Mapped["SorteoORM"] = relationship(back_populates="superbalota")


class ColorORM(Base):
    """Paleta de colores versionada por vigencia -- NO es un enum
    fijo, para poder reflejar cambios de reglamento sin romper el
    histórico de sorteos ya guardados."""

    __tablename__ = "colores"
    __table_args__ = (UniqueConstraint("juego_id", "codigo", "vigente_desde", name="uq_color_vigencia"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    juego_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("juegos.id"), nullable=False, index=True)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    vigente_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)

    juego: Mapped["JuegoORM"] = relationship(back_populates="colores")


class SorteoColorNumeroORM(Base):
    """Par (número, color) de una balota de ColorLoto. Se modela
    aparte de sorteo_numeros porque en ColorLoto el par es la unidad
    estadística, no el número o el color de forma aislada."""

    __tablename__ = "sorteo_color_numero"
    __table_args__ = (
        UniqueConstraint("sorteo_id", "posicion", name="uq_sorteo_color_numero_posicion"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    sorteo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sorteos.id"), nullable=False, index=True)
    color_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("colores.id"), nullable=False, index=True)
    numero: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    posicion: Mapped[int] = mapped_column(Integer, nullable=False)

    sorteo: Mapped["SorteoORM"] = relationship(back_populates="colores_numeros")
    color: Mapped["ColorORM"] = relationship()


class EstadisticaORM(Base):
    __tablename__ = "estadisticas"

    id: Mapped[uuid.UUID] = _uuid_pk()
    juego_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("juegos.id"), nullable=False, index=True)
    tipo_estadistica: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    hasta_numero_sorteo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parametros: Mapped[dict] = mapped_column(JSONB, default=dict)
    parametros_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resultado: Mapped[dict] = mapped_column(JSONB, default=dict)
    calculado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valido_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModeloORM(Base):
    __tablename__ = "modelos"

    id: Mapped[uuid.UUID] = _uuid_pk()
    juego_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("juegos.id"), nullable=False, index=True)
    nombre_modelo: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    hiperparametros: Mapped[dict] = mapped_column(JSONB, default=dict)
    metodo_validacion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entrenado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    metricas: Mapped[list["MetricaModeloORM"]] = relationship(
        back_populates="modelo", cascade="all, delete-orphan"
    )


class MetricaModeloORM(Base):
    """Filas, no un JSONB de métricas -- para poder ordenar/filtrar
    modelos por una métrica específica (ej. ranking por Brier
    Score) con una consulta SQL simple, sin parsear JSON."""

    __tablename__ = "metricas_modelo"

    id: Mapped[uuid.UUID] = _uuid_pk()
    modelo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modelos.id"), nullable=False, index=True)
    nombre_metrica: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    valor: Mapped[float] = mapped_column(Numeric, nullable=False)
    calculado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    modelo: Mapped["ModeloORM"] = relationship(back_populates="metricas")


class PrediccionORM(Base):
    __tablename__ = "predicciones"

    id: Mapped[uuid.UUID] = _uuid_pk()
    juego_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("juegos.id"), nullable=False, index=True)
    modelo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modelos.id"), nullable=False, index=True)
    fecha_generacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sorteo_objetivo: Mapped[int] = mapped_column(Integer, nullable=False)
    combinaciones: Mapped[list] = mapped_column(JSONB, default=list)
    numeros_fuertes: Mapped[list] = mapped_column(JSONB, default=list)
    numeros_debiles: Mapped[list] = mapped_column(JSONB, default=list)
    probabilidades: Mapped[dict] = mapped_column(JSONB, default=dict)
    explicacion: Mapped[str] = mapped_column(Text, default="")
    nivel_confianza: Mapped[float | None] = mapped_column(Numeric, nullable=True)


class SimulacionORM(Base):
    __tablename__ = "simulaciones"

    id: Mapped[uuid.UUID] = _uuid_pk()
    juego_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("juegos.id"), nullable=False, index=True)
    num_iteraciones: Mapped[int] = mapped_column(Integer, nullable=False)
    parametros: Mapped[dict] = mapped_column(JSONB, default=dict)
    resultado_resumen: Mapped[dict] = mapped_column(JSONB, default=dict)
    ejecutado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    duracion_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SincronizacionORM(Base):
    """Registro de cada ejecución del módulo de adquisición de datos.
    Alimenta el panel 'Importación' del dashboard."""

    __tablename__ = "sincronizaciones"

    id: Mapped[uuid.UUID] = _uuid_pk()
    juego_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("juegos.id"), nullable=False, index=True)
    conector: Mapped[str] = mapped_column(String(60), nullable=False)
    iniciado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    sorteos_nuevos: Mapped[int] = mapped_column(Integer, default=0)
    sorteos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    sorteos_duplicados: Mapped[int] = mapped_column(Integer, default=0)
    sorteos_incompletos: Mapped[int] = mapped_column(Integer, default=0)
    total_sorteos_encontrados: Mapped[int] = mapped_column(Integer, default=0)
    duracion_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ultimo_sorteo_importado: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalle_errores: Mapped[list] = mapped_column(JSONB, default=list)
