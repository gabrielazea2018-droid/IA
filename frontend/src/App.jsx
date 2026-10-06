import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Mapa from './components/Mapa.jsx'
import PanelLateral from './components/PanelLateral.jsx'
import { api } from './api.js'

const BOGOTA = { pos: [4.6097, -74.0817], zoom: 12 }
const DURACION_FLASH_MS = 4000

export default function App() {
  const [sitios, setSitios] = useState([])
  const [categorias, setCategorias] = useState([])
  const [stats, setStats] = useState({ total: 0, destacados: 0 })
  const [salud, setSalud] = useState(null)
  const [filtro, setFiltro] = useState(null)
  const [busqueda, setBusqueda] = useState('')
  const [seleccion, setSeleccion] = useState(null)
  const [cerca, setCerca] = useState(null) // { ids: Set, pos: [lat, lon] }
  const [geo, setGeo] = useState({ cargando: false, error: null })
  const [estado, setEstado] = useState({ cargando: true, error: null })

  // Mensaje efimero del panel (flash): se autolimpia tras unos segundos
  const [flash, setFlash] = useState(null)
  const temporizadorFlash = useRef(null)

  // Geocodificacion en vivo de una direccion que NO esta en la base
  const [dirEstado, setDirEstado] = useState({ cargando: false, error: null })
  const [direccion, setDireccion] = useState(null)

  // Punto azul pulsante de "mi ubicacion" (GPS del navegador)
  const [miUbicacion, setMiUbicacion] = useState(null)

  const avisar = useCallback((mensaje) => {
    setFlash(mensaje)
    clearTimeout(temporizadorFlash.current)
    temporizadorFlash.current = setTimeout(() => setFlash(null), DURACION_FLASH_MS)
  }, [])

  useEffect(() => () => clearTimeout(temporizadorFlash.current), [])

  // Carga inicial
  useEffect(() => {
    let vivo = true
    Promise.all([api.sitios(), api.categorias(), api.salud()])
      .then(([fc, cats, salud]) => {
        if (!vivo) return
        setSitios(fc.features)
        setCategorias(cats.categorias)
        setStats({ total: cats.total ?? fc.total ?? fc.features.length, destacados: cats.destacados ?? 0 })
        setSalud(salud)
        setEstado({ cargando: false, error: null })
      })
      .catch((err) => vivo && setEstado({ cargando: false, error: err.message }))
    return () => {
      vivo = false
    }
  }, [])

  // Recarga al cambiar filtros (con debounce en la busqueda)
  useEffect(() => {
    if (estado.error) return
    const id = setTimeout(() => {
      api
        .sitios({ categoria: filtro ?? undefined, q: busqueda || undefined })
        .then((fc) => setSitios(fc.features))
        .catch((err) => setEstado((e) => ({ ...e, error: err.message })))
    }, busqueda ? 300 : 0)
    return () => clearTimeout(id)
  }, [filtro, busqueda]) // eslint-disable-line react-hooks/exhaustive-deps

  const sitioSeleccionado = useMemo(
    () => sitios.find((s) => s.properties.id === seleccion) ?? null,
    [sitios, seleccion],
  )

  const destino = useMemo(() => {
    if (sitioSeleccionado) {
      const { lat, lon } = sitioSeleccionado.properties
      return { pos: [lat, lon], zoom: 16 }
    }
    if (direccion) return { pos: [direccion.lat, direccion.lon], zoom: 17 }
    if (cerca) return { pos: cerca.pos, zoom: 14 }
    return null
  }, [sitioSeleccionado, direccion, cerca])

  /** Geocodifica una direccion libre con el backend (nunca se guarda). */
  const buscarDireccion = useCallback(
    async (texto) => {
      const consulta = (texto ?? '').trim()
      if (!consulta) {
        setDirEstado({ cargando: false, error: 'Escribe una direccion de Bogota.' })
        return
      }
      setDirEstado({ cargando: true, error: null })
      setDireccion(null)
      try {
        const dir = await api.geocodificar(consulta)
        setDireccion(dir)
        setSeleccion(null)
        setCerca(null)
        setDirEstado({ cargando: false, error: null })
      } catch (err) {
        setDirEstado({ cargando: false, error: err.message })
      }
    },
    [],
  )

  /** Marca / desmarca un sitio como destacado (optimista, con rollback). */
  const alternarDestacado = useCallback(
    async (id) => {
      const anterior = sitios.find((s) => s.properties.id === id)
      if (!anterior) return
      const nuevo = !anterior.properties.destacado

      setSitios((lista) =>
        lista.map((f) =>
          f.properties.id === id
            ? { ...f, properties: { ...f.properties, destacado: nuevo } }
            : f,
        ),
      )
      setStats((s) => ({ ...s, destacados: Math.max(0, s.destacados + (nuevo ? 1 : -1)) }))

      try {
        const guardado = await api.destacado(id, nuevo)
        setSitios((lista) =>
          lista.map((f) =>
            f.properties.id === id
              ? { ...f, properties: { ...guardado.properties, distancia_m: f.properties.distancia_m } }
              : f,
          ),
        )
        avisar(
          `${guardado.properties.nombre}: ${
            nuevo ? 'marcado' : 'desmarcado'
          } como destacado`,
        )
      } catch (err) {
        // Revierte el cambio optimista si la API fallo
        setSitios((lista) =>
          lista.map((f) =>
            f.properties.id === id
              ? { ...f, properties: { ...f.properties, destacado: !nuevo } }
              : f,
          ),
        )
        setStats((s) => ({ ...s, destacados: Math.max(0, s.destacados + (nuevo ? -1 : 1)) }))
        avisar(`No se pudo actualizar el destacado: ${err.message}`)
      }
    },
    [sitios, avisar],
  )

  const buscarCercaDeMi = useCallback(() => {
    setGeo({ cargando: true, error: null })
    if (!navigator.geolocation) {
      setGeo({ cargando: false, error: 'Tu navegador no soporta geolocalizacion.' })
      return
    }
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        const pos = [coords.latitude, coords.longitude]
        setMiUbicacion(pos)
        try {
          const fc = await api.cerca({ lat: coords.latitude, lon: coords.longitude })
          setCerca({ ids: new Set(fc.features.map((f) => f.properties.id)), pos })
          setGeo({ cargando: false, error: null })
        } catch (err) {
          setGeo({ cargando: false, error: err.message })
        }
      },
      (err) => setGeo({ cargando: false, error: `No se pudo obtener tu ubicacion: ${err.message}` }),
      { timeout: 10000, enableHighAccuracy: true },
    )
  }, [])

  const limpiar = useCallback(() => {
    setFiltro(null)
    setBusqueda('')
    setSeleccion(null)
    setCerca(null)
    setGeo({ cargando: false, error: null })
    setDireccion(null)
    setDirEstado({ cargando: false, error: null })
    setMiUbicacion(null)
    setFlash(null)
    clearTimeout(temporizadorFlash.current)
  }, [])

  const seleccionarSitio = useCallback((id) => setSeleccion(id), [])

  return (
    <div className="app">
      <PanelLateral
        sitios={sitios}
        categorias={categorias}
        total={stats.total}
        stats={stats}
        filtro={filtro}
        setFiltro={setFiltro}
        busqueda={busqueda}
        setBusqueda={setBusqueda}
        onBuscarDireccion={buscarDireccion}
        dirEstado={dirEstado}
        direccion={direccion}
        seleccion={seleccion}
        onSeleccionar={seleccionarSitio}
        onDestacar={alternarDestacado}
        estado={estado}
        salud={salud}
        cerca={cerca}
        geo={geo}
        onCerca={buscarCercaDeMi}
        onLimpiar={limpiar}
        flash={flash}
      />
      <main className="mapa">
        <Mapa
          sitios={sitios}
          seleccion={seleccion}
          setSeleccion={setSeleccion}
          destino={destino}
          idsCerca={cerca?.ids ?? null}
          direccion={direccion}
          miUbicacion={miUbicacion}
          vistaInicial={BOGOTA}
        />
        {estado.error && (
          <div className="aviso-error" role="alert">
            <strong>No se pudo conectar con la API:</strong> {estado.error}
            <span>Verifica que el contenedor PostGIS y FastAPI esten levantados.</span>
          </div>
        )}
      </main>
    </div>
  )
}
