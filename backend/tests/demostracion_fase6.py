"""Demostración aislada de Fase 6, nunca datos/fuentes de un operador.

SQLite y repositorios/consumidores/modelos registrados son reales. El
proveedor y reloj son controlados; PostgreSQL/TaskScheduler requieren sus
ensayos nativos separados. No inicia Uvicorn ni instala programación.
"""
from __future__ import annotations
import argparse,json,platform,shutil,tempfile
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

from sqlalchemy.orm import Session
from app.application.use_cases.operacion_automatica import OperacionAutomatica
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.color import Color,ColorNumberPair
from app.domain.value_objects.combination import Combination
from app.infrastructure.repositories.sorteo_repository_sqlalchemy import SorteoRepositorySQLAlchemy
from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from tests.unit.test_fase6_integracion import entorno,detalle,_registrar_modelo,JUEGOS,Reloj
from tests.unit.test_ml_cinco_flujo import sin_entrenamiento
from tests.unit.fixtures_fase4 import arbol

DIAS=('lunes','martes','miercoles','jueves','viernes','sabado','domingo')

def _preparar(raiz,juego,reloj):
    t=entorno(raiz,juego,registrar=False)
    t.reloj.instante=reloj()
    for codigo in JUEGOS:
        filas=t.e.historicos[codigo]
        for i,r in enumerate(filas):
            fecha=date(2026,10,19)-timedelta(days=3*(len(filas)-1-i))
            filas[i]=replace(r,fecha=fecha,dia_semana=DIAS[fecha.weekday()])
        with Session(t.engine) as s:
            repo=SorteoRepositorySQLAlchemy(s);entidad=t.e.juegos.obtener_por_codigo(codigo)
            for r in filas:
                viejo=repo.obtener_por_numero(entidad.id,r.numero_sorteo)
                repo.actualizar(replace(viejo,fecha=r.fecha,dia_semana=r.dia_semana))
            s.commit()
    t.modelo,t.clave=_registrar_modelo(LaboratorioFileStore(t.ajustes.directorio_laboratorio_modelos),juego,t.e.historicos[juego])
    t.servicios[0].configurar(juego,t.modelo,2,'libre',17,registrado=t.clave)
    ultimo=t.e.historicos[juego][-1]
    t.conector.detalles={str(ultimo.numero_sorteo):detalle(juego,ultimo)}
    return t

def demostrar(salida):
    raiz=Path(tempfile.mkdtemp(prefix='f6d '));resultado={'plataforma':platform.platform(),'tipo_ensayo':'sintetico_portable_sin_TaskScheduler',
        'proveedor':'controlado, sin red','BD':'SQLite propia; no acredita advisory PostgreSQL',
        'programacion':'invocación directa repetida independiente de Uvicorn; TaskScheduler se valida aparte'}
    entornos={}
    try:
        reloj=Reloj(datetime(2026,10,20,12,tzinfo=timezone.utc))
        for i,j in enumerate(JUEGOS):
            p=raiz/str(i);p.mkdir();entornos[j]=_preparar(p,j,reloj)
        class Multipuerto:
            def por_juego(self,codigo):return entornos[codigo].adaptador.por_juego(codigo)
        store=AlmacenAutomatizacion(raiz/'a');store.actualizar_configuracion({'activada':True,'pausada':False})
        servicio=OperacionAutomatica(store,Multipuerto(),reloj=reloj)
        modelos={j:arbol(Path(t.ajustes.directorio_laboratorio_modelos)) for j,t in entornos.items()}
        with sin_entrenamiento():
            previa=servicio.ciclo(origen='demostracion_previa')
            assert previa['estado']=='exito',previa
            reloj.instante=datetime(2026,10,23,4,10,tzinfo=timezone.utc)
            for j,t in entornos.items():
                t.reloj.instante=reloj()
                fechas=[date(2026,10,20),date(2026,10,22)] if j=='MILOTO' else [date(2026,10,22) if j=='COLORLOTO' else date(2026,10,21)]
                filas=t.e.siguiente(j,cantidad=len(fechas))
                t.conector.detalles={str(r.numero_sorteo):replace(detalle(j,r),fecha=f) for r,f in zip(filas,fechas)}
            ciclo=servicio.ciclo(forzar=True,origen='demostracion_desatendida')
            assert ciclo['estado']=='exito',ciclo
            fuentes={}
            for j,t in entornos.items():
                anterior=previa['juegos'][j]['objetivo']
                filas=t.servicios[2].emisiones(j)['filas']
                assert any(f['objetivo']==anterior and f['estado']=='incluido' for f in filas)
                assert arbol(Path(t.ajustes.directorio_laboratorio_modelos))==modelos[j]
                fuentes[j]={'objetivo_anterior_observado':anterior,'ultimo_sorteo':ciclo['juegos'][j]['ultimo_sorteo'],
                    'objetivo_siguiente':ciclo['juegos'][j]['objetivo'],'modelo':t.modelo,'version':t.clave,
                    'cartera':ciclo['juegos'][j]['prediccion']['cartera']['clave'],
                    'explicacion':ciclo['juegos'][j]['prediccion']['explicacion']}
            repetida=servicio.ciclo(forzar=True,origen='demostracion_repetida')
            assert repetida['estado']=='exito'
            for j in JUEGOS:
                assert repetida['juegos'][j]['prediccion']['cartera']['clave']==fuentes[j]['cartera']
                assert repetida['juegos'][j]['prediccion']['explicacion']['estado']=='reutilizada'
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.automatizacion_dependencies import get_automatizacion
        from app.api.web.routers import automatizacion
        app=FastAPI();app.include_router(automatizacion.router);app.dependency_overrides[get_automatizacion]=lambda:servicio
        antes=arbol(raiz)
        with TestClient(app,base_url='http://localhost') as c:
            panel=c.get('/automatizacion');assert panel.status_code==200
            assert c.get('/automatizacion').status_code==200
        assert arbol(raiz)==antes
        salida.parent.mkdir(parents=True,exist_ok=True);salida.with_name('panel-e2e.html').write_text(panel.text,encoding='utf-8')
        servicio.pausar();consultas=sum(len(t.conector.listados) for t in entornos.values())
        assert servicio.ciclo()['estado']=='pausada'
        assert sum(len(t.conector.listados) for t in entornos.values())==consultas
        reiniciada=OperacionAutomatica(AlmacenAutomatizacion(raiz/'a'),Multipuerto(),reloj=reloj)
        assert reiniciada.panel()['estado']=='pausada' and len(reiniciada.panel()['ejecuciones'])==3
        resultado.update(estado='aprobado',juegos=fuentes,cuatro_juegos=True,modelos_congelados_reales=4,
            ciclos=3,asociacion_resultados_anteriores=True,reutilizacion_exacta=True,GET_sin_escrituras=True,
            pausa_sin_consultas=True,estado_persistente_tras_reconstruir_servicio=True,sin_reentrenar_en_ciclo=True)
    except BaseException as error:
        resultado.update(estado='error',tipo=type(error).__name__,error=str(error),temporal_pendiente=str(raiz))
        raise
    finally:
        for t in entornos.values():t.engine.dispose()
        if resultado.get('estado')=='aprobado':
            try:shutil.rmtree(raiz);resultado['limpieza']='completa'
            except OSError as e:resultado.update(limpieza='pendiente',temporal_pendiente=str(raiz),aviso_limpieza=type(e).__name__)
        salida.parent.mkdir(parents=True,exist_ok=True);salida.write_text(json.dumps(resultado,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return resultado

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--salida',type=Path,required=True);args=p.parse_args(argv)
    r=demostrar(args.salida);print(json.dumps(r,ensure_ascii=False));return 0 if r['estado']=='aprobado' else 1

if __name__=='__main__':raise SystemExit(main())
