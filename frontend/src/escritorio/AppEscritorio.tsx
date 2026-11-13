import { createContext, useContext, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { consultar, obtenerJuegos, rutaApi } from "../api/cliente";
import { fechaHora } from "../api/formatos";
import { decCarterasGuardadas, decResultadosGuardados, delContexto, type ResultadosGuardados } from "../api/guardados";
import { decPredicciones, type Juego, type Prediccion } from "../api/presentacion";
import { TablaDesplazable, VerResultado } from "../componentes/comunes";
import { Consulta } from "../componentes/Estados";
import { useConsulta } from "../usos/consulta";
import { FormularioApuesta, MisApuestas, type SeleccionDeApuesta } from "./Apuestas";
import { decComparacion, decEstadoReferencia, decOrigen, type Fuente } from "./consultas";
import "./escritorio.css";

const SECCIONES = ["Predicciones", "Historial de aciertos", "Comparación de modelos", "Sincronización", "Mis apuestas"] as const;
type Seccion = (typeof SECCIONES)[number];
const RegistroDeApuesta = createContext<((seleccion: SeleccionDeApuesta) => void) | null>(null);
type LineaResultadoGuardado = ResultadosGuardados["lineas"][number];
const fecha = (valor: string | null) => valor === null ? "—" : fechaHora(valor);
const legible = (valor: string) => valor.replaceAll("_", " ");
const contarSorteos = (n: number) => `${n} ${n === 1 ? "sorteo" : "sorteos"}`;

function Detalle({ juego, prediccion: p, version }: { juego: Juego; prediccion: Prediccion; version: number | null }) {
  const registrar = useContext(RegistroDeApuesta);
  const observado = p.observado;
  const resultado = observado?.estado === "observado" ? observado.resultado : null;
  const cambiado = observado?.historico_hasta_el_corte === "cambio";
  const aciertos = resultado === null ? null : observado?.aciertos ?? null;
  return <article className="visor-panel">
    <div className="visor-detalle">
      <div><h3>{p.modelo.nombre ?? p.modelo.id ?? "Modelo sin identificar"}</h3>
        <p className="text-body-secondary mb-0">Objetivo {p.objetivo} · Corte {p.corte ?? "—"} · Emisión {fecha(p.generado_en)}</p></div>
      <span className="visor-estado">{p.registrado ? `Registro v${p.registrado.numero}` : "Registro no informado"}</span>
    </div>
    {cambiado && <p className="alert alert-warning mt-3">El histórico hasta el corte difiere del utilizado al emitir.</p>}
    {resultado ? <div className="visor-resultado"><strong>Resultado cargado en la referencia</strong><VerResultado resultado={resultado} /></div>
      : <p className="visor-resultado mb-0">{observado?.estado === "pendiente" ? "Resultado pendiente"
        : observado?.estado === "sin_base" ? "Base no disponible" : "Resultado no disponible"}</p>}
    <TablaDesplazable etiqueta="Combinaciones guardadas y aciertos">
      <table className="table align-middle mb-0">
        <thead><tr><th scope="col">Línea</th><th scope="col">Combinación</th>{aciertos && <th scope="col">Aciertos</th>}
          {registrar && <th scope="col">Apuesta</th>}</tr></thead>
        <tbody>{p.combinaciones.map((c) => {
          const acierto = aciertos?.por_linea.find((a) => a.linea === c.linea);
          return <tr key={c.linea}><td>{c.linea}{c.papel ? <span className="d-block small text-body-secondary">{legible(c.papel)}</span> : null}</td>
            <td><VerResultado resultado={c.resultado} /></td>
            {aciertos && <td>{acierto ? `${acierto.aciertos} / ${juego.cantidad_numeros}` : "—"}
              {acierto?.superbalota != null && <span className="d-block small">Superbalota {acierto.superbalota ? "acertada" : "sin acierto"}</span>}</td>}
            {registrar && <td><button type="button" className="btn btn-outline-secondary btn-sm"
              aria-label={`Registrar apuesta de la línea ${c.linea}`}
              onClick={() => registrar({ juego, prediccion: p, linea: c, versionCartera: version })}>Registrar apuesta</button></td>}
          </tr>;
        })}</tbody>
      </table>
    </TablaDesplazable>
  </article>;
}

function Cartera({ juego, clave, version }: { juego: Juego; clave: string; version: number | null }) {
  const url = rutaApi(["juegos", juego.codigo, "predicciones"], { cartera: clave, historial: "0" });
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url,
    delContexto(decPredicciones, juego.codigo, { clave, leer: (d) => ({ juego: d.juego, clave: d.prediccion?.clave ?? "" }) }), s));
  return <Consulta estado={estado} reintentar={reintentar} que="la cartera guardada">
    {(datos) => datos.prediccion ? <Detalle juego={juego} prediccion={datos.prediccion} version={version} /> : <p>Cartera no disponible.</p>}
  </Consulta>;
}

function Carteras({ juego, objetivo, preferida, historial = false }: {
  juego: Juego; objetivo: number | null; preferida?: string; historial?: boolean;
}) {
  const [pagina, cambiarPagina] = useState(1);
  const [linea, cambiarLinea] = useState("");
  const [clave, seleccionar] = useState("");
  const filtro = objetivo === null ? null : String(objetivo);
  const url = rutaApi(["juegos", juego.codigo, "carteras-guardadas"], {
    desde: filtro, hasta: filtro, pagina: String(pagina), por_pagina: "20", linea: linea || null,
  });
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, delContexto(decCarterasGuardadas, juego.codigo), s));
  return <Consulta estado={estado} reintentar={reintentar} que="las carteras guardadas">{(datos) => {
    const disponibles = datos.elementos.filter((c) => c.estado === "disponible");
    const actual = disponibles.find((c) => c.clave === clave)
      ?? disponibles.find((c) => c.clave === preferida) ?? disponibles[0];
    return <>
      <div className="visor-filtros">
        {historial && <label>Línea del modelo<select className="form-select" value={linea} onChange={(e) => {
          cambiarLinea(e.target.value); cambiarPagina(1); seleccionar("");
        }}><option value="">Todas</option>{datos.lineas.map((l) => <option key={l} value={l}>{l}</option>)}</select></label>}
        {actual && <label>Cartera guardada<select className="form-select" value={actual.clave} onChange={(e) => seleccionar(e.target.value)}>
          {disponibles.map((c) => <option key={c.clave} value={c.clave}>
            {c.nombre ?? c.modelo} · sorteo {c.objetivo} · cartera v{c.version} · {c.clave.slice(0, 8)}
          </option>)}
        </select></label>}
      </div>
      {datos.elementos.some((c) => c.estado === "alterado") && <p className="alert alert-warning">Hay carteras alteradas en esta página.</p>}
      {datos.paginas > 1 && <div className="visor-paginacion" aria-label="Páginas de carteras">
        <button className="btn btn-outline-secondary btn-sm" disabled={datos.pagina === 1} onClick={() => cambiarPagina(datos.pagina - 1)}>Anterior</button>
        <span>Página {datos.pagina} de {datos.paginas}</span>
        <button className="btn btn-outline-secondary btn-sm" disabled={datos.pagina >= datos.paginas} onClick={() => cambiarPagina(datos.pagina + 1)}>Siguiente</button>
      </div>}
      {actual ? <Cartera juego={juego} clave={actual.clave} version={actual.version ?? null} /> : <p>Sin emisiones guardadas para esta selección.</p>}
    </>;
  }}</Consulta>;
}

function Predicciones({ juego }: { juego: Juego }) {
  const url = rutaApi(["juegos", juego.codigo, "predicciones"], { historial: "0" });
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, delContexto(decPredicciones, juego.codigo), s));
  return <Consulta estado={estado} reintentar={reintentar} que="el objetivo de la predicción">{(datos) => {
    const guardada = datos.prediccion;
    const objetivo = datos.base.objetivo ?? guardada?.objetivo ?? null;
    if (objetivo === null) return <p>Sin objetivo disponible en la referencia.</p>;
    return <>
      <p className="text-body-secondary">{datos.base.objetivo === null ? "Último objetivo guardado" : "Siguiente objetivo de la referencia"} · {objetivo}</p>
      {datos.base.objetivo === null && <p>El corte actual de la base no está disponible.</p>}
      <Carteras key={objetivo} juego={juego} objetivo={objetivo} preferida={guardada?.objetivo === objetivo ? guardada.clave : undefined} />
    </>;
  }}</Consulta>;
}

function Historial({ juego }: { juego: Juego }) {
  const [objetivo, fijarObjetivo] = useState<number | null>(null);
  function filtrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const valor = new FormData(evento.currentTarget).get("sorteo");
    fijarObjetivo(valor ? Number(valor) : null);
  }
  return <>
    <form className="visor-filtros" onSubmit={filtrar}>
      <label>Sorteo<input className="form-control" type="number" min="1" step="1" name="sorteo" placeholder="Todos" /></label>
      <button className="btn btn-marca" type="submit">Filtrar</button>
    </form>
    <Carteras key={objetivo ?? "todos"} juego={juego} objetivo={objetivo} historial />
  </>;
}

const nombreLinea = (l: LineaResultadoGuardado) => [l.nombre, l.procedencia, l.registrado ? `registro v${l.registrado.numero}` : l.perfil]
  .filter(Boolean).join(" · ");

function AciertosComparados({ juego, lineas, tipo }: { juego: Juego; lineas: LineaResultadoGuardado[]; tipo: string }) {
  const parametros = new URLSearchParams({ tipo });
  for (const l of lineas) parametros.append("linea", l.clave);
  const url = `${rutaApi(["escritorio", "juegos", juego.codigo, "comparacion"])}?${parametros}`;
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, delContexto(decComparacion, juego.codigo), s));
  return <Consulta estado={estado} reintentar={reintentar} que="la comparación">{({ comparacion, resumenes }) => {
    const n = comparacion.objetivos_comunes.length;
    const filas = lineas.map((l) => ({ l, comun: comparacion.por_linea[l.clave]?.aciertos,
      individual: resumenes[l.clave]?.aciertos }));
    const ordenable = n > 0 && filas.every((f) => f.comun?.objetivos === n && f.comun.de === juego.cantidad_numeros);
    const empate = ordenable && new Set(filas.map((f) => f.comun?.suma)).size === 1;
    if (ordenable) filas.sort((a, b) => (b.comun?.suma ?? 0) - (a.comun?.suma ?? 0));
    return <div className="visor-panel">
      <p>{n === 0 ? "Sin muestra común para esta selección." : `Muestra común de ${contarSorteos(n)}.`}
        {ordenable ? " Aciertos de la sugerencia emitida." : " Se muestran los datos disponibles por línea."}
        {empate && " Empate en la muestra."}</p>
      <TablaDesplazable etiqueta="Comparación de aciertos por modelo"><table className="table mb-0">
        <thead><tr><th scope="col">Modelo y procedencia</th><th scope="col">Aciertos en la muestra común</th><th scope="col">Historial de la línea</th></tr></thead>
        <tbody>{filas.map(({ l, comun, individual }) => <tr key={l.clave}><th scope="row">{nombreLinea(l)}</th>
          <td>{comun ? `${comun.suma} en ${contarSorteos(comun.objetivos)}` : "—"}</td>
          <td>{individual ? `${individual.suma} en ${contarSorteos(individual.objetivos)}` : "Sin aciertos por sugerencia informados"}</td></tr>)}</tbody>
      </table></TablaDesplazable>
    </div>;
  }}</Consulta>;
}

function ElegirLineas({ juego, lineas, preferidas, tipo }: {
  juego: Juego; lineas: LineaResultadoGuardado[]; preferidas: LineaResultadoGuardado[]; tipo: string;
}) {
  const [primera, cambiarPrimera] = useState(preferidas[0]?.clave ?? "");
  const [segunda, cambiarSegunda] = useState(preferidas[1]?.clave ?? "");
  const a = lineas.find((l) => l.clave === primera);
  const b = lineas.find((l) => l.clave === segunda);
  if (lineas.length < 2) return <p>Se necesitan dos líneas guardadas para comparar.</p>;
  return <>
    <div className="visor-filtros">
      <label>Primer modelo<select className="form-select" value={primera} onChange={(e) => cambiarPrimera(e.target.value)}>
        {lineas.map((l) => <option key={l.clave} value={l.clave} disabled={l.clave === segunda}>{nombreLinea(l)}</option>)}
      </select></label>
      <label>Segundo modelo<select className="form-select" value={segunda} onChange={(e) => cambiarSegunda(e.target.value)}>
        {lineas.map((l) => <option key={l.clave} value={l.clave} disabled={l.clave === primera}>{nombreLinea(l)}</option>)}
      </select></label>
    </div>
    {a && b && a !== b && <AciertosComparados juego={juego} lineas={[a, b]} tipo={tipo} />}
  </>;
}

function Comparacion({ juego }: { juego: Juego }) {
  const [tipo, cambiarTipo] = useState("seguimiento");
  const url = rutaApi(["juegos", juego.codigo, "resultados"], { tipo, por_pagina: "1" });
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, delContexto(decResultadosGuardados, juego.codigo), s));
  return <>
    <div className="visor-filtros"><label>Tipo de evaluación<select className="form-select" value={tipo} onChange={(e) => cambiarTipo(e.target.value)}>
      <option value="seguimiento">Seguimiento</option><option value="retrospectiva">Retrospectiva</option>
    </select></label></div>
    <Consulta estado={estado} reintentar={reintentar} que="las líneas de modelos">{(datos) => {
      const preferidas = datos.lineas.filter((l) => datos.resumenes[l.clave]?.aciertos != null);
      const ordenadas = [...new Set([...preferidas, ...datos.lineas])];
      return <ElegirLineas key={tipo} juego={juego} lineas={datos.lineas} preferidas={ordenadas} tipo={tipo} />;
    }}</Consulta>
  </>;
}

function Sincronizacion({ juegos }: { juegos: Juego[] }) {
  const url = rutaApi(["escritorio", "sincronizacion"]);
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, decEstadoReferencia, s));
  return <>
    <button type="button" className="btn btn-outline-secondary mb-3" onClick={reintentar}>Recargar vista</button>
    <Consulta estado={estado} reintentar={reintentar} que="el estado de sincronización">{(datos) => <div className="visor-panel">
      {datos.datos === "sinteticos" && <p>Referencia sintética preparada el {fecha(datos.fecha_referencia)}</p>}
      <TablaDesplazable etiqueta="Sincronización por juego"><table className="table mb-0">
        <thead><tr><th scope="col">Juego</th><th scope="col">Último sorteo</th><th scope="col">Última comprobación</th><th scope="col">Última importación</th></tr></thead>
        <tbody>{datos.juegos.map((j) => <tr key={j.juego}>
          <th scope="row">{juegos.find((x) => x.codigo === j.juego)?.nombre ?? j.juego}</th>
          <td>{j.ultimo_sorteo ?? "—"}<span className="d-block text-body-secondary small">{j.total_sorteos} cargados</span></td>
          <td>{legible(j.estado_fase6)}<span className="d-block text-body-secondary small">{fecha(j.ultima_comprobacion)}</span></td>
          <td>{j.sincronizacion ? <>{legible(j.sincronizacion.estado)} · {j.sincronizacion.sorteos_nuevos} nuevos
            <span className="d-block text-body-secondary small">{fecha(j.sincronizacion.finalizado_en ?? j.sincronizacion.iniciado_en)}</span></> : "Sin intentos registrados"}</td>
        </tr>)}</tbody>
      </table></TablaDesplazable>
    </div>}</Consulta>
  </>;
}

function AppEscritorio({ fuente, apuestas }: { fuente: Fuente; apuestas: ReturnType<typeof decOrigen>["apuestas"] }) {
  const [seccion, cambiarSeccion] = useState<Seccion>("Predicciones");
  const [codigo, cambiarJuego] = useState("BALOTO");
  const [cierre, cambiarCierre] = useState<"abierto" | "solicitando" | "solicitado" | "fallo">("abierto");
  const [seleccion, seleccionarApuesta] = useState<SeleccionDeApuesta | null>(null);
  const [apuestaGuardada, avisarGuardada] = useState(false);
  const [estado, reintentar] = useConsulta("juegos", obtenerJuegos);
  function navegar(seccion: Seccion) {
    cambiarSeccion(seccion);
    seleccionarApuesta(null);
    avisarGuardada(false);
  }
  function registrar(nueva: SeleccionDeApuesta) {
    cambiarSeccion("Mis apuestas");
    seleccionarApuesta(nueva);
    avisarGuardada(false);
  }
  async function cerrar() {
    cambiarCierre("solicitando");
    try {
      const respuesta = await fetch("/api/v1/escritorio/cerrar", { method: "POST", cache: "no-store", redirect: "error" });
      cambiarCierre(respuesta.status === 204 ? "solicitado" : "fallo");
    } catch {
      cambiarCierre("fallo");
    }
  }
  if (cierre === "solicitado") return <main className="visor-ancho visor-cuerpo">
    <h1>Lotería Predictor</h1><p role="status">Cierre solicitado. La consola mostrará el resultado del ensayo.</p>
  </main>;
  return <RegistroDeApuesta.Provider value={apuestas ? registrar : null}><div className="visor">
    <a href="#contenido" className="salto">Saltar al contenido</a>
    <header className="visor-cabecera"><div className="visor-ancho">
      <h1>Lotería Predictor</h1>
      <div className="d-flex align-items-center gap-2 flex-wrap">
        <span className="visor-estado">{fuente === "fase6" ? "Datos reales de Fase 6" : "Datos sintéticos"}</span>
        <button className="btn btn-outline-light btn-sm" type="button" disabled={cierre === "solicitando"} onClick={cerrar}>Cerrar piloto</button>
      </div>
    </div></header>
    <main id="contenido" className="visor-ancho visor-cuerpo">
      {cierre === "fallo" && <p className="alert alert-warning" role="alert">No se pudo solicitar el cierre. Puedes pulsar Ctrl+C en la consola del piloto.</p>}
      <nav className="visor-nav" aria-label="Consulta de escritorio">{SECCIONES.filter((s) => apuestas || s !== "Mis apuestas").map((s) =>
        <button key={s} type="button" aria-current={s === seccion ? "page" : undefined} onClick={() => navegar(s)}>{s}</button>)}</nav>
      <section aria-labelledby="vista-titulo"><h2 id="vista-titulo">{seccion}</h2>
        <Consulta estado={estado} reintentar={reintentar} que="los juegos">{(juegos) => {
          if (seccion === "Sincronización") return <Sincronizacion juegos={juegos} />;
          if (seccion === "Mis apuestas" && apuestas) {
            return seleccion ? <FormularioApuesta seleccion={seleccion} juegos={juegos} parejas={apuestas.parejas}
              cancelar={() => seleccionarApuesta(null)} guardar={() => {
                seleccionarApuesta((actual) => actual === seleccion ? null : actual);
                avisarGuardada(true);
              }} /> : <>
              {apuestaGuardada && <p className="alert alert-success" role="status">Apuesta guardada.</p>}
              <MisApuestas juegos={juegos} />
            </>;
          }
          const juego = juegos.find((j) => j.codigo === codigo) ?? juegos[0];
          if (!juego) return <p>Sin juegos disponibles.</p>;
          return <>
            <div className="visor-filtros"><label>Juego<select aria-label="Juego" className="form-select" value={juego.codigo} onChange={(e) => cambiarJuego(e.target.value)}>
              {juegos.map((j) => <option value={j.codigo} key={j.codigo}>{j.nombre}</option>)}
            </select></label></div>
            {seccion === "Predicciones" && <Predicciones key={juego.codigo} juego={juego} />}
            {seccion === "Historial de aciertos" && <Historial key={juego.codigo} juego={juego} />}
            {seccion === "Comparación de modelos" && <Comparacion key={juego.codigo} juego={juego} />}
          </>;
        }}</Consulta>
      </section>
      <footer className="visor-pie">Predicciones experimentales · experimental_no_acreditado</footer>
    </main>
  </div></RegistroDeApuesta.Provider>;
}

export async function montarEscritorio(elemento: HTMLElement) {
  const inicio = new URLSearchParams(location.hash.slice(1)).get("inicio");
  if (inicio !== null) history.replaceState(null, "", location.pathname + location.search);
  const raiz = createRoot(elemento);
  try {
    if (inicio !== null) {
      const respuesta = await fetch("/escritorio/sesion", { method: "POST", headers: { "X-Arranque-Escritorio": inicio },
        cache: "no-store", redirect: "error", referrerPolicy: "no-referrer" });
      if (respuesta.status !== 204) throw new Error("sesión no disponible");
    }
    const origen = await consultar("/escritorio/origen", decOrigen, AbortSignal.timeout(5000));
    raiz.render(<AppEscritorio fuente={origen.datos} apuestas={origen.apuestas} />);
  } catch {
    raiz.render(<main className="visor-ancho visor-cuerpo"><h1>Lotería Predictor</h1><p role="alert">Abre el piloto desde su lanzador.</p></main>);
  }
}
