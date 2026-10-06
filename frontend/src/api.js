/**
 * Cliente minimo de la API (sin librerias extra).
 *
 * En desarrollo, Vite hace proxy de `/api` hacia FastAPI (ver vite.config.js).
 * En contenedor, nginx deriva `/api` al servicio `backend`.
 * Si sirves el build en otro host, define `VITE_API_URL`.
 */
const BASE = import.meta.env.VITE_API_URL ?? ''

async function solicitud(ruta, opciones) {
  const res = await fetch(`${BASE}${ruta}`, opciones)
  if (!res.ok) {
    const detalle = await res.json().catch(() => ({}))
    throw new Error(
      typeof detalle.detail === 'string' ? detalle.detail : `Error ${res.status}`,
    )
  }
  return res.json()
}

const get = (ruta) => solicitud(ruta)

const patch = (ruta, cuerpo) =>
  solicitud(ruta, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cuerpo),
  })

export const api = {
  salud: () => get('/api/salud'),
  categorias: () => get('/api/categorias'),

  /** Listado GeoJSON con filtros opcionales. */
  sitios: ({ categoria, q } = {}) => {
    const params = new URLSearchParams()
    if (categoria) params.set('categoria', categoria)
    if (q) params.set('q', q)
    const qs = params.toString()
    return get(`/api/sitios${qs ? `?${qs}` : ''}`)
  },

  /** Sitios dentro de un radio (ST_DWithin en el backend). */
  cerca: ({ lat, lon, radio_m = 1500 }) =>
    get(
      `/api/cerca?lat=${lat}&lon=${lon}&radio_m=${radio_m}` +
        `&limite=${Math.min(50, 1) * 50}`,
    ),

  /** Geocodificacion en vivo de una direccion libre (proxy de Nominatim). */
  geocodificar: (q) => get(`/api/geocodificar?q=${encodeURIComponent(q)}`),

  /** Marca / desmarca un sitio como destacado. */
  destacado: (id, valor) =>
    patch(`/api/sitios/${id}/destacado`, { destacado: valor }),
}

/** Enlace externo para trazar la ruta en Google Maps. */
export const enlaceRuta = (lat, lon) =>
  `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`
