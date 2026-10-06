import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import { colorDe, iconoDe } from '../categorias.js'
import { enlaceRuta } from '../api.js'

/** Construye el marcador "pin" con el icono de su categoria dentro. */
function pin({ color, icono, clases = [], estrella = false }) {
  const badge = estrella
    ? '<span class="pin__estrella"><i class="fa-solid fa-star"></i></span>'
    : ''
  return L.divIcon({
    className: 'contenedor-pin',
    html:
      '<div class="pin-escena">' +
      `<div class="pin ${clases.filter(Boolean).join(' ')}" style="--c:${color}">` +
      `<i class="fa-solid ${icono}"></i></div>${badge}</div>`,
    iconSize: [28, 36],
    iconAnchor: [14, 33],
    popupAnchor: [0, -30],
  })
}

/** Marcador de direccion geocodificada (busqueda libre, no guardada). */
const pinDireccion = L.divIcon({
  className: 'contenedor-pin',
  html:
    '<div class="pin-escena">' +
    '<div class="pin pin--direccion"><i class="fa-solid fa-location-crosshairs"></i></div>' +
    '<span class="pin__estrella pin__estrella--osm"><i class="fa-solid fa-cloud"></i></span>' +
    '</div>',
  iconSize: [30, 38],
  iconAnchor: [15, 35],
  popupAnchor: [0, -32],
})

/** Marcador pulsante de "mi ubicacion" (GPS del navegador). */
const pinUbicacion = L.divIcon({
  className: 'contenedor-pin',
  html:
    '<div class="mi-ubicacion">' +
    '<span class="mi-ubicacion__halo"></span>' +
    '<span class="mi-ubicacion__punto"><i class="fa-solid fa-location-dot"></i></span>' +
    '</div>',
  iconSize: [46, 46],
  iconAnchor: [23, 23],
  popupAnchor: [0, -24],
})

function Enfocar({ destino }) {
  const map = useMap()
  useEffect(() => {
    if (destino) map.flyTo(destino.pos, destino.zoom, { duration: 0.8 })
  }, [map, destino])
  return null
}

export default function Mapa({
  sitios,
  seleccion,
  setSeleccion,
  destino,
  idsCerca,
  direccion,
  miUbicacion,
  vistaInicial,
}) {
  const refs = useRef(new Map())
  const refDireccion = useRef(null)
  const refUbicacion = useRef(null)

  // Al elegir un sitio desde el panel se abre su popup
  useEffect(() => {
    if (seleccion != null) refs.current.get(seleccion)?.openPopup()
  }, [seleccion, sitios])

  // Tras el flyTo de una direccion buscada, abrimos su popup
  useEffect(() => {
    if (direccion) refDireccion.current?.openPopup()
  }, [direccion])

  // Igual para el punto de "mi ubicacion"
  useEffect(() => {
    if (miUbicacion) refUbicacion.current?.openPopup()
  }, [miUbicacion])

  const features = useMemo(() => sitios, [sitios])

  return (
    <MapContainer
      center={vistaInicial.pos}
      zoom={vistaInicial.zoom}
      className="leaflet-host"
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Enfocar destino={destino} />

      {features.map((f) => {
        const p = f.properties
        const color = colorDe(p.categoria)
        const destacado = Boolean(p.destacado)
        const activo = p.id === seleccion
        const cercano = idsCerca?.has(p.id) ?? false
        const clases = [
          destacado && 'pin--destacado',
          activo && 'pin--activo',
          cercano && 'pin--cerca',
        ]
        return (
          <Marker
            key={p.id}
            ref={(m) => {
              if (m) refs.current.set(p.id, m)
              else refs.current.delete(p.id)
            }}
            position={[p.lat, p.lon]}
            icon={pin({
              color,
              icono: iconoDe(p.categoria),
              clases,
              estrella: destacado,
            })}
            zIndexOffset={destacado ? 500 : activo ? 300 : cercano ? 100 : 0}
            eventHandlers={{
              click: () => setSeleccion(p.id),
              popupclose: () => setSeleccion((actual) => (actual === p.id ? null : actual)),
            }}
          >
            <Popup>
              <div className="popup">
                <div className="popup__cabecera">
                  <span className="popup__icono" style={{ background: color }}>
                    <i className={`fa-solid ${iconoDe(p.categoria)}`} />
                  </span>
                  <div>
                    <span className="popup__chip">{p.categoria}</span>
                    <h3>
                      {p.nombre}
                      {destacado && (
                        <i
                          className="fa-solid fa-star popup__estrella"
                          title="Sitio destacado"
                        />
                      )}
                    </h3>
                  </div>
                </div>
                {p.descripcion && <p>{p.descripcion}</p>}
                {p.direccion && (
                  <small className="popup__dir">
                    <i className="fa-solid fa-location-dot" /> {p.direccion}
                  </small>
                )}
                <div className="popup__meta">
                  <span>
                    {p.lat.toFixed(5)}, {p.lon.toFixed(5)}
                  </span>
                  <a href={enlaceRuta(p.lat, p.lon)} target="_blank" rel="noreferrer">
                    Cómo llegar <i className="fa-solid fa-route" />
                  </a>
                </div>
              </div>
            </Popup>
          </Marker>
        )
      })}

      {direccion && (
        <Marker
          ref={refDireccion}
          position={[direccion.lat, direccion.lon]}
          icon={pinDireccion}
          zIndexOffset={900}
        >
          <Popup>
            <div className="popup popup--direccion">
              <span className="popup__chip popup__chip--osm">Dirección buscada</span>
              <h3>{direccion.direccion}</h3>
              <p className="popup__nota">
                <i className="fa-solid fa-circle-info" /> Resultado de OpenStreetMap
                {direccion.aproximado ? (
                  <>
                    {' '}(<strong>punto aproximado</strong>, Nominatim no indexa esa
                    puerta).
                  </>
                ) : (
                  <>.</>
                )}
                <strong> No está guardado</strong> en la base de datos.
              </p>
              <div className="popup__meta">
                <span>
                  {direccion.lat.toFixed(5)}, {direccion.lon.toFixed(5)}
                </span>
                <a
                  href={enlaceRuta(direccion.lat, direccion.lon)}
                  target="_blank"
                  rel="noreferrer"
                >
                  Cómo llegar <i className="fa-solid fa-route" />
                </a>
              </div>
            </div>
          </Popup>
        </Marker>
      )}

      {miUbicacion && (
        <Marker
          ref={refUbicacion}
          position={miUbicacion}
          icon={pinUbicacion}
          zIndexOffset={1000}
        >
          <Popup>
            <div className="popup popup--ubicacion">
              <span className="popup__chip popup__chip--geo">Mi ubicación</span>
              <p className="popup__nota">
                Punto detectado por el GPS del navegador ({miUbicacion[0].toFixed(5)},{' '}
                {miUbicacion[1].toFixed(5)}).
              </p>
            </div>
          </Popup>
        </Marker>
      )}
    </MapContainer>
  )
}
