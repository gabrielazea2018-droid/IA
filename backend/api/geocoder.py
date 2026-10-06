"""Geocodificacion en vivo contra Nominatim (OpenStreetMap).

El frontend necesita localizar **cualquier direccion de Bogota**, no solo los
sitios guardados en la base.  En vez de llamar a Nominatim desde el navegador
(a donde no se puede enviar un ``User-Agent`` identificable ni controlar la
tasa), el backend actua de proxy:

* concentra el ``User-Agent`` y respeta la politica de 1 consulta/segundo de
  Nominatim;
* restringe la busqueda a la bounding box de Bogota (``viewbox``) y filtra el
  resultado final con la misma caja, para no devolver homonimos de otras
  ciudades;
* si la frase literal no da resultados, prueba variantes (sin ciudade, sin
  tildes y podando palabras del final).  Nominatim no geocodifica bien frases
  largas: ``"Universidad Distrital Facultad de Ingenieria, Bogota"`` da 0
  resultados, mientras ``"Universidad Distrital Facultad"`` si encuentra la
  Facultad de la UDistrital.  Cuando el match viene de una variante se marca
  ``aproximado=True`` para que la UI lo indique;
* cachea los resultados en memoria para no repetir llamadas.
"""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request

from ..core.config import BOGOTA_BBOX, settings

NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
USER_AGENT = settings.user_agent

# viewbox de Nominatim: (izquierda, arriba, derecha, abajo)
BOGOTA_VIEWBOX = (
    BOGOTA_BBOX["min_lon"],
    BOGOTA_BBOX["max_lat"],
    BOGOTA_BBOX["max_lon"],
    BOGOTA_BBOX["min_lat"],
)

_MINIMO_INTERVALO_S = 1.1  # politica de uso publico de Nominatim
_MAX_PODAS = 4  # palabras que se pueden quitar del final de la frase
_TAMANO_CACHE = 500

# Palabras funcionales que no aportan a la hora de comprobar la coincidencia
_STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "y", "o", "a", "en", "con", "por",
    "para", "al", "un", "una", "unos", "unas", "no", "n", "numero", "num",
    "bogota", "colombia", "d.c", "dc",
}

_cache: dict[str, dict | None] = {}
_candado = threading.Lock()
_ultima_llamada = 0.0


def _dentro_de_bogota(lat: float, lon: float) -> bool:
    b = BOGOTA_BBOX
    return b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _relevantes(texto: str) -> list[str]:
    """Palabras con contenido (sin stopwords ni tildes) de una consulta."""
    salida: list[str] = []
    for token in re.split(r"[\s,]+", texto.lower().strip(" ,;.")):
        token = _sin_tildes(token)
        if not token or token in _STOPWORDS:
            continue
        if token not in salida:
            salida.append(token)
    return salida


def _display_normalizado(display: str) -> str:
    return _sin_tildes(display.lower())


def _contiene(display_limpio: str, palabra: str) -> bool:
    """Coincidencia por palabra completa (``40`` no casa dentro de ``Carrera``)."""
    return re.search(rf"(?<!\w){re.escape(palabra)}(?!\w)", display_limpio) is not None


def _numero_de(texto: str) -> str | None:
    """Extrae el numero de puerta tipo ``40-62`` de una direccion bogotana."""
    m = re.search(r"\b(\d{1,3}\s*[-–]\s*\d{1,3})\b", texto)
    return m.group(1).replace("–", "-").replace(" ", "") if m else None


def _variantes(consulta: str) -> list[tuple[str, bool]]:
    """Genera consultas alternativas, de la mas exacta a la mas laxa.

    Devuelve pares ``(texto, es_poda)`` sin repetidos.  Las consultas marcadas
    como *poda* (frases recortadas) tienen que demostrar ademas que las palabras
    que quedan aparecen en el resultado; sin eso, "Plaza Mayor de Madrid"
    acabaria devolviendo la Plaza de Bolivar.
    """
    base = " ".join(consulta.split()).strip(" ,;.")
    variantes: list[tuple[str, bool]] = []

    def add(texto: str, poda: bool) -> None:
        limpio = " ".join(texto.split()).strip(" ,;.")
        if len(limpio) < 3:
            return
        if any(limpio.lower() == v[0].lower() for v in variantes):
            return
        variantes.append((limpio, poda))

    add(base, False)
    if not re.search(r"(?i)bogot", base):
        add(f"{base}, Bogotá", False)
    add(_sin_tildes(base), False)

    # Podas del final: Nominatim a veces no encuentra frases largas, y al
    # quitar palabras del final aun conserva el sujeto principal.
    tokens = [t for t in re.split(r"[,\s]+", base) if t]
    for n in range(1, min(_MAX_PODAS + 1, len(tokens))):
        resto = tokens[: len(tokens) - n]
        if len(resto) >= 2:
            add(" ".join(resto), True)

    return variantes


def _consultar(texto: str) -> list[dict]:
    """Llama a Nominatim y devuelve los candidatos (serializa a 1 req/s)."""
    global _ultima_llamada

    params = {
        "q": texto,
        "format": "jsonv2",
        "limit": 5,
        "addressdetails": 1,
        "accept-language": "es",
        "countrycodes": "co",
        "viewbox": ",".join(str(v) for v in BOGOTA_VIEWBOX),
        "bounded": 0,  # ordena por proximidad; el filtro real se hace abajo
    }
    url = f"{NOMINATIM_SEARCH}?{urllib.parse.urlencode(params)}"

    espera = _MINIMO_INTERVALO_S - (time.monotonic() - _ultima_llamada)
    if espera > 0:
        time.sleep(espera)

    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    finally:
        _ultima_llamada = time.monotonic()

    return list(datos) if isinstance(datos, list) else []


def buscar_direccion(consulta: str) -> dict | None:
    """Geocodifica una direccion libre y devuelve ``None`` si no hay match.

    Devuelve ``{lat, lon, direccion, ciudad, completa, aproximado, fuente}``.
    Solo se aceptan puntos dentro de la bounding box de Bogota D.C.

    Reglas de aceptacion:

    * la consulta exacta se acepta si el punto cae dentro de Bogota **y el
      resultado se llama Bogota** (la bounding box es generosa y alcanza a
      Neiva o Soacha);
    * una consulta **podada** (frase recortada) solo se acepta si sus palabras
      con contenido aparecen en el nombre que devuelve Nominatim -- evita que
      "Plaza Mayor de Madrid" termine en la Plaza de Bolivar;
    * si la direccion trae numero de puerta (``40-62``) se priorizan los
      candidatos que lo traen; si ninguno lo trae el resultado se marca
      ``aproximado`` (Nominatim rara vez indexa puertas en Bogota).
    """
    clave = consulta.strip().lower()
    if not clave:
        return None

    with _candado:
        if clave in _cache:
            return _cache[clave]

        numero = _numero_de(consulta)
        encontrado: dict | None = None

        for texto, poda in _variantes(consulta):
            candidatos = _consultar(texto)
            if not candidatos:
                continue

            if numero:
                candidatos = sorted(
                    candidatos,
                    key=lambda it: numero
                    not in _display_normalizado(it.get("display_name", "")),
                )

            relevantes = _relevantes(texto)
            for item in candidatos:
                display = item.get("display_name", "")
                limpio = _display_normalizado(display)
                lat, lon = float(item["lat"]), float(item["lon"])

                if not _dentro_de_bogota(lat, lon):
                    continue
                # La caja es generosa (tambien cubre municipios vecinos): exige
                # ademas que el propio resultado se llame Bogota, para que una
                # consulta de otra ciudad no termine marcando un punto aqui.
                if "bogot" not in limpio:
                    continue
                if poda and not all(_contiene(limpio, p) for p in relevantes):
                    continue

                aproximada = poda or (
                    numero is not None and not _contiene(limpio, numero)
                )
                partes = [p.strip() for p in display.split(",")]
                encontrado = {
                    "lat": lat,
                    "lon": lon,
                    "direccion": ", ".join(partes[:3]),
                    "ciudad": ", ".join(partes[3:6]) or "Bogotá",
                    "completa": display,
                    "aproximado": aproximada,
                    "fuente": "OpenStreetMap / Nominatim",
                }
                break
            if encontrado:
                break

        if len(_cache) >= _TAMANO_CACHE:
            _cache.clear()
        _cache[clave] = encontrado
        return encontrado
