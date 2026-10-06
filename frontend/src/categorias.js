/**
 * Paleta e iconografia por categoria.
 *
 * `CATEGORIAS` concentra el color y el icono (clase Font Awesome 6 Free,
 * paquete `@fortawesome/fontawesome-free`) de cada categoria.  Los helpers
 * `colorDe` / `iconoDe` son los que usan el mapa y el panel lateral.
 */

export const CATEGORIAS = {
  Cultura: { color: '#8b5cf6', icono: 'fa-palette' },
  Historia: { color: '#f59e0b', icono: 'fa-archway' },
  Naturaleza: { color: '#10b981', icono: 'fa-tree' },
  Deporte: { color: '#3b82f6', icono: 'fa-futbol' },
  Gastronomia: { color: '#ef4444', icono: 'fa-utensils' },
  Comercial: { color: '#ec4899', icono: 'fa-bag-shopping' },
  Educacion: { color: '#06b6d4', icono: 'fa-graduation-cap' },
  Religion: { color: '#94a3b8', icono: 'fa-church' },
  Gobierno: { color: '#64748b', icono: 'fa-building-columns' },
  Transporte: { color: '#f97316', icono: 'fa-plane' },
  Entretenimiento: { color: '#eab308', icono: 'fa-ticket' },
  Salud: { color: '#f43f5e', icono: 'fa-heart-pulse' },
}

/** Colores planos (compatibilidad con los imports existentes). */
export const COLORES = Object.fromEntries(
  Object.entries(CATEGORIAS).map(([k, v]) => [k, v.color]),
)

/** Icono Font Awesome por defecto para categorias desconocidas. */
const ICONO_POR_DEFECTO = 'fa-location-dot'

/** Color de un marcador a partir de su categoria. */
export const colorDe = (categoria) => CATEGORIAS[categoria]?.color ?? '#6366f1'

/** Clase de icono Font Awesome (sin el prefijo `fa-solid`) de una categoria. */
export const iconoDe = (categoria) => CATEGORIAS[categoria]?.icono ?? ICONO_POR_DEFECTO

/** Icono completo listo para pegar en un `<i class="...">`. */
export const claseIcono = (categoria) => `fa-solid ${iconoDe(categoria)}`

const normalizar = (s) =>
  (s ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')

const INDICE = new Map(
  Object.entries(CATEGORIAS).map(([nombre, { color, icono }]) => [
    normalizar(nombre),
    { color, icono },
  ]),
)

/** Igual que `colorDe`, pero ignora acentos y mayusculas. */
export const colorDeTolerante = (categoria) =>
  INDICE.get(normalizar(categoria))?.color ?? colorDe(categoria)

/** Igual que `iconoDe`, pero ignora acentos y mayusculas. */
export const iconoDeTolerante = (categoria) =>
  INDICE.get(normalizar(categoria))?.icono ?? iconoDe(categoria)

/** Icono Font Awesome de elementos especiales del visor. */
export const ICONOS = {
  ubicacion: 'fa-solid fa-location-dot',
  direccion: 'fa-solid fa-location-crosshairs',
  destacado: 'fa-solid fa-star',
  cerca: 'fa-solid fa-person-walking-arrow-right',
  buscar: 'fa-solid fa-magnifying-glass-location',
}
