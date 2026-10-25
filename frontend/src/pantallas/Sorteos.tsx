/** Sorteos: filtros y paginacion en la URL (GET /juegos/{codigo}/sorteos) y detalle de uno. */
import { type FormEvent, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { consultar, rutaApi } from "../api/cliente";
import { decPaginaDeSorteos, decSorteo, type Sorteo } from "../api/presentacion";
import { Numeros, ParColor, TablaDesplazable } from "../componentes/comunes";
import { Consulta } from "../componentes/Estados";
import { useFiltros } from "../componentes/Filtros";
import { PestanasDeJuego } from "../componentes/Marco";
import { useConsulta } from "../usos/consulta";

const FILTROS = ["desde", "hasta", "numero_desde", "numero_hasta", "orden", "por_pagina", "pagina"] as const;
type Filtro = (typeof FILTROS)[number];

const ORDENES: Readonly<Record<string, string>> = {
  fecha_desc: "Fecha (más reciente primero)",
  fecha_asc: "Fecha (más antiguo primero)",
  numero_desc: "Número (mayor primero)",
  numero_asc: "Número (menor primero)",
};

function Combinacion({ s }: { s: Sorteo }) {
  if (s.pares.length > 0) {
    return (
      <span className="d-inline-flex flex-wrap">
        {s.pares.map((p, i) => (
          <ParColor key={i} numero={p.numero} color={p.color_codigo} nombre={p.color_nombre} />
        ))}
      </span>
    );
  }
  return <Numeros numeros={s.numeros} superbalota={s.superbalota} />;
}

function FormularioDeSorteos({
  valores,
  aplicar,
}: {
  valores: Record<Filtro, string | null>;
  aplicar: (nuevos: Partial<Record<Filtro, string | null>>) => void;
}) {
  const [borrador, setBorrador] = useState(() => ({ ...valores }));
  const campo = (n: Filtro) => ({
    id: `filtro-${n}`,
    value: borrador[n] ?? "",
    onChange: (e: { target: { value: string } }) => setBorrador((b) => ({ ...b, [n]: e.target.value })),
  });
  const enviar = (e: FormEvent) => {
    e.preventDefault();
    aplicar({ ...borrador, pagina: null });
  };
  return (
    <form className="row g-2 align-items-end mb-3" onSubmit={enviar} aria-label="Filtros de sorteos">
      <div className="col-6 col-md-2">
        <label className="form-label small mb-0" htmlFor="filtro-desde">
          Desde (fecha)
        </label>
        <input className="form-control form-control-sm" type="date" {...campo("desde")} />
      </div>
      <div className="col-6 col-md-2">
        <label className="form-label small mb-0" htmlFor="filtro-hasta">
          Hasta (fecha)
        </label>
        <input className="form-control form-control-sm" type="date" {...campo("hasta")} />
      </div>
      <div className="col-6 col-md-2">
        <label className="form-label small mb-0" htmlFor="filtro-numero_desde">
          Desde el sorteo n.º
        </label>
        <input className="form-control form-control-sm" type="number" min={1} {...campo("numero_desde")} />
      </div>
      <div className="col-6 col-md-2">
        <label className="form-label small mb-0" htmlFor="filtro-numero_hasta">
          Hasta el sorteo n.º
        </label>
        <input className="form-control form-control-sm" type="number" min={1} {...campo("numero_hasta")} />
      </div>
      <div className="col-8 col-md-2">
        <label className="form-label small mb-0" htmlFor="filtro-orden">
          Orden
        </label>
        <select className="form-select form-select-sm" {...campo("orden")}>
          <option value="">Predeterminado (fecha descendente)</option>
          {Object.entries(ORDENES).map(([v, t]) => (
            <option key={v} value={v}>
              {t}
            </option>
          ))}
        </select>
      </div>
      <div className="col-4 col-md-1">
        <label className="form-label small mb-0" htmlFor="filtro-por_pagina">
          Por página
        </label>
        <input className="form-control form-control-sm" type="number" min={1} max={100} {...campo("por_pagina")} />
      </div>
      <div className="col-12 col-md-1">
        <button className="btn btn-sm btn-marca w-100" type="submit">
          Filtrar
        </button>
      </div>
    </form>
  );
}

export function Paginacion({ pagina, paginas, enlace }: { pagina: number; paginas: number; enlace: (p: number) => string }) {
  if (paginas <= 1) {
    return null;
  }
  const items: { p: number; texto: string; etiqueta: string }[] = [];
  if (pagina > 1) {
    items.push({ p: 1, texto: "«", etiqueta: "Primera página" }, { p: pagina - 1, texto: "‹", etiqueta: "Página anterior" });
  }
  items.push({ p: pagina, texto: String(pagina), etiqueta: `Página ${pagina} de ${paginas}` });
  if (pagina < paginas) {
    items.push({ p: pagina + 1, texto: "›", etiqueta: "Página siguiente" }, { p: paginas, texto: "»", etiqueta: "Última página" });
  }
  return (
    <nav aria-label="Paginación">
      <ul className="pagination pagination-sm flex-wrap">
        {items.map((i) => (
          <li className={`page-item${i.p === pagina ? " active" : ""}`} key={`${i.texto}-${i.p}`}>
            {i.p === pagina ? (
              <span className="page-link" aria-current="page" aria-label={i.etiqueta}>
                {i.texto}
              </span>
            ) : (
              <Link className="page-link" to={enlace(i.p)} aria-label={i.etiqueta}>
                {i.texto}
              </Link>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function Sorteos() {
  const { codigo = "" } = useParams();
  const [valores, cambiar] = useFiltros(FILTROS);
  const [parametros] = useSearchParams();
  const url = rutaApi(["juegos", codigo, "sorteos"], valores);
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, decPaginaDeSorteos, s));
  const enlace = (p: number) => {
    const siguiente = new URLSearchParams(parametros);
    siguiente.set("pagina", String(p));
    return `?${siguiente.toString()}`;
  };
  const filtrado = FILTROS.some((n) => n !== "pagina" && n !== "por_pagina" && n !== "orden" && valores[n] !== null);
  return (
    <>
      <PestanasDeJuego codigo={codigo} />
      <h1 className="h3">Sorteos</h1>
      <FormularioDeSorteos key={parametros.toString()} valores={valores} aplicar={cambiar} />
      <Consulta estado={estado} reintentar={reintentar} que="los sorteos">
        {(pagina) =>
          pagina.sorteos.length === 0 ? (
            <div className="alert alert-info" data-estado="vacio">
              {filtrado ? "Ningún sorteo cumple los filtros." : "No hay sorteos cargados para este juego."} (total {pagina.total})
            </div>
          ) : (
            <>
              <p className="small text-muted" aria-live="polite">
                {pagina.total} sorteos · página {pagina.pagina} de {pagina.paginas} · {pagina.por_pagina} por página
              </p>
              <TablaDesplazable etiqueta="Sorteos">
                <table className="table table-sm table-striped">
                  <thead>
                    <tr>
                      <th scope="col" className="text-end">
                        Sorteo
                      </th>
                      <th scope="col">Fecha</th>
                      <th scope="col">Día</th>
                      <th scope="col">Resultado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagina.sorteos.map((s) => (
                      <tr key={s.numero_sorteo}>
                        <td className="text-end">
                          <Link to={`/juegos/${encodeURIComponent(codigo)}/sorteos/${s.numero_sorteo}`}>{s.numero_sorteo}</Link>
                        </td>
                        <td className="text-nowrap">{s.fecha}</td>
                        <td>{s.dia_semana}</td>
                        <td>
                          <Combinacion s={s} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TablaDesplazable>
              <div className="mt-2">
                <Paginacion pagina={pagina.pagina} paginas={pagina.paginas} enlace={enlace} />
              </div>
            </>
          )
        }
      </Consulta>
    </>
  );
}

export function DetalleSorteo() {
  const { codigo = "", numero = "" } = useParams();
  const url = rutaApi(["juegos", codigo, "sorteos", numero]);
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, decSorteo, s));
  return (
    <>
      <PestanasDeJuego codigo={codigo} />
      <h1 className="h3">Sorteo {numero}</h1>
      <Consulta estado={estado} reintentar={reintentar} que="el sorteo">
        {(s) => (
          <div className="card stat-card p-3">
            <dl className="row mb-0">
              <dt className="col-sm-3">Número</dt>
              <dd className="col-sm-9">{s.numero_sorteo}</dd>
              <dt className="col-sm-3">Fecha</dt>
              <dd className="col-sm-9">
                {s.fecha} ({s.dia_semana})
              </dd>
              <dt className="col-sm-3">{s.pares.length > 0 ? "Pares número-color" : "Números"}</dt>
              <dd className="col-sm-9">
                <Combinacion s={s} />
              </dd>
              {s.pares.length === 0 ? (
                <>
                  <dt className="col-sm-3">Superbalota</dt>
                  <dd className="col-sm-9">{s.superbalota === null ? "no aplica en este juego o sorteo" : s.superbalota}</dd>
                </>
              ) : null}
            </dl>
          </div>
        )}
      </Consulta>
      <p className="small mt-3">
        <Link to={`/juegos/${encodeURIComponent(codigo)}/sorteos`}>Volver a los sorteos</Link>
      </p>
    </>
  );
}
