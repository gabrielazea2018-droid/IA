import { useEffect, useState } from 'react'
import { claseIcono, colorDe, ICONOS } from '../categorias.js'

/** Contador animado (cuenta de 0 a `valor` con easing). */
function useContador(valor, duracion = 800) {
  const [n, setN] = useState(0)

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    let raf = 0
    const t0 = performance.now()
    const paso = (t) => {
      const k = Math.min(1, (t - t0) / duracion)
      const suave = 1 - Math.pow(1 - k, 3) // easeOutCubic
      setN(Math.round(valor * suave))
      if (k < 1) raf = requestAnimationFrame(paso)
    }
    raf = requestAnimationFrame(paso)
    return () => cancelAnimationFrame(raf)
  }, [valor, duracion])

  return n
}

function Chip({ nombre, total, activo, onClick }) {
  return (
    <button
      type="button"
      className={`chip ${activo ? 'chip--activo' : ''}`}
      style={{ '--c': colorDe(nombre) }}
      onClick={onClick}
      aria-pressed={activo}
    >
      <i className={claseIcono(nombre)} />
      <span className="chip__nombre">{nombre}</span>
      <span className="chip__total">{total}</span>
    </button>
  )
}

function Tarjeta({ p, activo, cercano, onSeleccionar, onDestacar }) {
  const color = colorDe(p.categoria)
  const destacado = Boolean(p.destacado)
  const clases = [
    'tarjeta',
    activo && 'tarjeta--activa',
    cercano && 'tarjeta--cerca',
    destacado && 'tarjeta--destacada',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button type="button" className={clases} onClick={() => onSeleccionar(p.id)}>
      <span className="tarjeta__icono" style={{ background: color }}>
        <i className={claseIcono(p.categoria)} />
      </span>

      <span className="tarjeta__cuerpo">
        <strong>
          {p.nombre}
          {destacado && <i className="fa-solid fa-star tarjeta__estrella" />}
        </strong>
        <small className="tarjeta__cat" style={{ color }}>
          {p.categoria}
        </small>
        <span className="tarjeta__dir">
          <i className="fa-solid fa-location-dot" /> {p.direccion ?? '—'}
        </span>
        {cercano && typeof p.distancia_m === 'number' && (
          <span className="tarjeta__dist">{p.distancia_m} m de ti</span>
        )}
      </span>

      <span
        role="button"
        tabIndex={0}
        title={destacado ? 'Quitar de destacados' : 'Marcar como destacado'}
        aria-label={destacado ? 'Quitar de destacados' : 'Marcar como destacado'}
        className={`tarjeta__estrella-boton ${destacado ? 'es-activa' : ''}`}
        onClick={(e) => {
          e.stopPropagation()
          onDestacar(p.id)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            e.stopPropagation()
            onDestacar(p.id)
          }
        }}
      >
        <i className="fa-solid fa-star" />
      </span>
    </button>
  )
}

export default function PanelLateral({
  sitios,
  categorias,
  total,
  stats,
  filtro,
  setFiltro,
  busqueda,
  setBusqueda,
  onBuscarDireccion,
  dirEstado,
  direccion,
  seleccion,
  onSeleccionar,
  onDestacar,
  estado,
  salud,
  cerca,
  geo,
  onCerca,
  onLimpiar,
  flash,
}) {
  const hayFiltro = Boolean(filtro || busqueda || cerca || direccion)

  const nSitios = useContador(stats?.total ?? 0)
  const nCategorias = useContador(categorias.length)
  const nDestacados = useContador(stats?.destacados ?? 0)

  const enviarDireccion = () => onBuscarDireccion(busqueda)

  return (
    <aside className="panel">
      <header className="panel__cabecera">
        <div className="panel__logo">
          <i className="fa-solid fa-map-location-dot" />
        </div>
        <div>
          <h1>Sitios de Interés</h1>
          <p>Bogotá D.C. · PostgreSQL + PostGIS</p>
        </div>
      </header>

      {/* ---------- Barra de estadisticas animada ---------- */}
      <div className="stats" role="status" aria-label="Resumen del visor">
        <div className="stat">
          <span className="stat__icono stat__icono--sitios">
            <i className="fa-solid fa-location-dot" />
          </span>
          <span className="stat__texto">
            <b>{nSitios}</b>
            <small>sitios</small>
          </span>
        </div>
        <div className="stat">
          <span className="stat__icono stat__icono--cats">
            <i className="fa-solid fa-shapes" />
          </span>
          <span className="stat__texto">
            <b>{nCategorias}</b>
            <small>categorías</small>
          </span>
        </div>
        <div className="stat">
          <span className="stat__icono stat__icono--dest">
            <i className="fa-solid fa-star" />
          </span>
          <span className="stat__texto">
            <b>{nDestacados}</b>
            <small>destacados</small>
          </span>
        </div>
      </div>

      {/* ---------- Buscador: filtra la BD y geocodifica direcciones ---------- */}
      <div className="buscador">
        <div className="buscador__caja">
          <i className="fa-solid fa-magnifying-glass buscador__lupa" />
          <input
            type="search"
            placeholder="Buscar sitio o dirección de Bogotá…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') enviarDireccion()
            }}
            aria-label="Buscar sitios o direcciones"
          />
          <button
            type="button"
            className="buscador__boton"
            onClick={enviarDireccion}
            disabled={dirEstado.cargando}
            title="Buscar esta dirección en OpenStreetMap (no se guarda)"
            aria-label="Buscar dirección en el mapa"
          >
            <i
              className={
                dirEstado.cargando
                  ? 'fa-solid fa-circle-notch fa-spin'
                  : ICONOS.buscar
              }
            />
          </button>
        </div>
        <p className="buscador__ayuda">
          Filtra los sitios guardados · pulsa <kbd>Intro</kbd> para geocodificar la
          dirección en el mapa
        </p>
      </div>

      {dirEstado.error && <p className="aviso aviso--error">{dirEstado.error}</p>}
      {direccion && !dirEstado.error && (
        <p className="aviso aviso--dir">
          <i className="fa-solid fa-location-crosshairs" />{' '}
          <span>
            <strong>{direccion.direccion}</strong> · marcador temporal (no guardado)
            {direccion.aproximado ? ' · punto aproximado' : ''}
          </span>
        </p>
      )}

      {/* ---------- Chips de categoria ---------- */}
      <div className="chips">
        <button
          type="button"
          className={`chip chip--todos ${!filtro ? 'chip--activo' : ''}`}
          onClick={() => setFiltro(null)}
        >
          <i className="fa-solid fa-border-all" />
          <span className="chip__nombre">Todas</span>
          <span className="chip__total">{stats?.total ?? 0}</span>
        </button>
        {categorias.map((c) => (
          <Chip
            key={c.nombre}
            nombre={c.nombre}
            total={c.total}
            activo={filtro === c.nombre}
            onClick={() => setFiltro(filtro === c.nombre ? null : c.nombre)}
          />
        ))}
      </div>

      {/* ---------- Acciones ---------- */}
      <div className="acciones">
        <button
          type="button"
          className="boton boton--primario"
          onClick={onCerca}
          disabled={geo.cargando}
        >
          <i
            className={
              geo.cargando
                ? 'fa-solid fa-circle-notch fa-spin'
                : 'fa-solid fa-person-walking-arrow-right'
            }
          />
          {geo.cargando ? 'Localizando…' : 'Sitios cerca de mí'}
        </button>
        {hayFiltro && (
          <button
          type="button"
          className="boton boton--suave"
          onClick={onLimpiar}
        >
          <i className="fa-solid fa-eraser" /> Limpiar
        </button>
        )}
      </div>

      {geo.error && <p className="aviso aviso--error">{geo.error}</p>}
      {flash && <p className="aviso aviso--flash">{flash}</p>}
      {cerca && !geo.error && (
        <p className="aviso aviso--ok">
          <i className="fa-solid fa-location-dot" /> Tu ubicación está marcada en azul
          y {cerca.ids.size} sitio{cerca.ids.size === 1 ? '' : 's'} cercano
          {cerca.ids.size === 1 ? '' : 's'} resaltado{cerca.ids.size === 1 ? '' : 's'}.
        </p>
      )}

      {/* ---------- Lista de sitios ---------- */}
      <div className="lista">
        {estado.cargando && <p className="vacio">Cargando sitios…</p>}
        {estado.error && (
          <p className="vacio">
            Sin conexión con la API. Levanta el contenedor y el backend para ver los
            sitios.
          </p>
        )}
        {!estado.cargando && !estado.error && sitios.length === 0 && (
          <p className="vacio">No hay resultados para esa búsqueda.</p>
        )}
        {sitios.map((f) => {
          const p = f.properties
          return (
            <Tarjeta
              key={p.id}
              p={p}
              activo={p.id === seleccion}
              cercano={Boolean(cerca?.ids.has(p.id))}
              onSeleccionar={onSeleccionar}
              onDestacar={onDestacar}
            />
          )
        })}
      </div>

      <footer className="pie">
        <span>
          {estado.cargando ? '…' : `${sitios.length}${hayFiltro ? ` de ${total}` : ''} sitios`}
        </span>
        {salud && <span title={`Base: ${salud.base}`}>PostGIS {salud.postgis.split(' ')[0]}</span>}
      </footer>
    </aside>
  )
}
