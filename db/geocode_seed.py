"""Genera db/init.sql con los sitios de interes de Bogota.

Geocodifica cada sitio contra Nominatim (OpenStreetMap) para obtener
coordenadas reales, valida que el resultado caiga dentro de Bogota D.C.
y que el nombre del elemento coincida, y escribe el SQL que se ejecuta
la primera vez que levanta el contenedor de PostGIS.

Los resultados se cachean en db/geocache.json para poder regenerar el
SQL sin volver a consultar Nominatim.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

NOMINATIM = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "bogota-sitios-interes-demo/1.0"
OUT_DIR = Path(__file__).resolve().parent
CACHE_FILE = OUT_DIR / "geocache.json"

# Bounding box de Bogota D.C. (izquierda, arriba, derecha, abajo)
BOGOTA_VIEWBOX = (-74.30, 5.00, -73.85, 4.40)

# Cada sitio define:
#   busquedas: consultas en orden hasta obtener un match valido
#   ancla:     (lat, lon, tolerancia_grados) aproximada de referencia
#   validar:   subcadenas que DEBEN aparecer en el nombre del resultado
#   rechazar:  subcadenas que NO deben aparecer (evita droguerias, etc.)
SITIOS = [
    {
        "nombre": "Plaza de Bolivar",
        "categoria": "Historia",
        "busquedas": ["Plaza de Bolívar, Bogotá"],
        "descripcion": "Plaza principal de Bogotá, escenario de la independencia y sede de la Catedral, el Capitolio y el Palacio de Nariño.",
        "direccion": "Carrera 7 con Calle 11",
        "ancla": (4.598, -74.076, 0.01),
        "validar": ["plaza de bolívar"],
        "rechazar": [],
    },
    {
        "nombre": "Catedral Primada de Bogota",
        "categoria": "Religion",
        "busquedas": ["Catedral Primada de Bogotá"],
        "descripcion": "Catedral neogótica del siglo XVI, panteón del conquistador Gonzalo Jiménez de Quesada.",
        "direccion": "Plaza de Bolívar, Cra. 7 #11-43",
        "ancla": (4.598, -74.075, 0.01),
        "validar": ["catedral primada"],
        "rechazar": [],
    },
    {
        "nombre": "Capitolio Nacional",
        "categoria": "Gobierno",
        "busquedas": ["Capitolio Nacional de Colombia"],
        "descripcion": "Sede del Congreso de la República, ejemplo de arquitectura neoclásica del siglo XIX.",
        "direccion": "Cra. 7 #8-69",
        "ancla": (4.597, -74.077, 0.01),
        "validar": ["capitolio"],
        "rechazar": [],
    },
    {
        "nombre": "Casa de Narino",
        "categoria": "Gobierno",
        "busquedas": ["Casa de Nariño, Bogotá"],
        "descripcion": "Residencia oficial del Presidente de Colombia, construida en el siglo XVIII.",
        "direccion": "Carrera 6 #9-53",
        "ancla": (4.596, -74.077, 0.01),
        "validar": ["nariño"],
        "rechazar": [],
    },
    {
        "nombre": "Teatro Colon",
        "categoria": "Cultura",
        "busquedas": ["Teatro Colón, Bogotá"],
        "descripcion": "Teatro a la italiana inaugurado en 1895, patrono monumento nacional.",
        "direccion": "Cra. 6 #3-69",
        "ancla": (4.597, -74.075, 0.01),
        "validar": ["teatro colón"],
        "rechazar": [],
    },
    {
        "nombre": "Museo del Oro",
        "categoria": "Cultura",
        "busquedas": ["Museo del Oro, Bogotá"],
        "descripcion": "Museo del Banco de la República con más de 34.000 piezas de oro, cerámica y textil de los pueblos indígenas.",
        "direccion": "Carrera 6 #15-80",
        "ancla": (4.602, -74.072, 0.01),
        "validar": ["museo del oro"],
        "rechazar": [],
    },
    {
        "nombre": "Museo Nacional de Colombia",
        "categoria": "Cultura",
        "busquedas": ["Museo Nacional de Colombia"],
        "descripcion": "Museo de historia de Colombia alojado en un antiguo panóptico (cárcel distrital) de 1897.",
        "direccion": "Cra. 7 #25-50",
        "ancla": (4.615, -74.068, 0.02),
        "validar": ["museo nacional"],
        "rechazar": [],
    },
    {
        "nombre": "Museo de Arte Moderno",
        "categoria": "Cultura",
        "busquedas": ["Museo de Arte Moderno de Bogotá"],
        "descripcion": "Colección de arte colombiano e internacional del siglo XX y XXI, en el Parque Independencia.",
        "direccion": "Cra. 7 #25-85",
        "ancla": (4.610, -74.069, 0.02),
        "validar": ["museo de arte moderno"],
        "rechazar": [],
    },
    {
        "nombre": "Planetario Distrital de Bogota",
        "categoria": "Cultura",
        "busquedas": ["Planetario de Bogotá", "Planetario Distrital de Bogotá"],
        "descripcion": "Sala de proyecciones y exposiciones de astronomía y ciencia junto al Parque Independencia.",
        "direccion": "Av. El Dorado #24-86",
        "ancla": (4.612, -74.070, 0.03),
        "validar": ["planetario"],
        "rechazar": [],
    },
    {
        "nombre": "Maloka",
        "categoria": "Cultura",
        "busquedas": ["Maloka, Bogotá", "Centro Interactivo Maloka"],
        "descripcion": "Centro interactivo de ciencia y tecnología con domo de proyección.",
        "direccion": "Cra. 69 con Calle 24B",
        "ancla": (4.65, -74.11, 0.08),
        "validar": ["maloka"],
        "rechazar": [],
    },
    {
        "nombre": "Museo de Arte Colonial",
        "categoria": "Cultura",
        "busquedas": ["Museo de Arte Colonial de Bogotá"],
        "descripcion": "Arte colonial religioso y civil de los siglos XVI a XIX en el casco histórico de La Candelaria.",
        "direccion": "Cra. 5 #26-66",
        "ancla": (4.597, -74.075, 0.01),
        "validar": ["museo de arte colonial"],
        "rechazar": [],
    },
    {
        "nombre": "Plaza de Toros Santamaria",
        "categoria": "Cultura",
        "busquedas": [
            "Plaza de Toros Santamaría, Bogotá",
            "Plaza Santamaría, Bogotá",
            "Santamaría, Bogotá",
        ],
        "descripcion": "Torera inaugurada en 1931, hoy sede de conciertos y eventos masivos.",
        "direccion": "Cra. 15 #67-32",
        "ancla": (4.63, -74.075, 0.05),
        "validar": ["santamaría"],
        "rechazar": ["iglesia", "capilla"],
    },
    {
        "nombre": "Biblioteca Virgilio Barco",
        "categoria": "Cultura",
        "busquedas": ["Biblioteca Virgilio Barco"],
        "descripcion": "Biblioteca distrital de estilo brutalista rodeada de zonas verdes.",
        "direccion": "Cra. 60 con Calle 57",
        "ancla": (4.65, -74.09, 0.05),
        "validar": ["virgilio barco"],
        "rechazar": [],
    },
    {
        "nombre": "Barrio La Candelaria",
        "categoria": "Historia",
        "busquedas": ["La Candelaria, Bogotá", "UPZ La Candelaria, Bogotá"],
        "descripcion": "Barrio histórico de casas coloniales, museos, universidades y café tradicional.",
        "direccion": "La Candelaria, Bogotá",
        "ancla": (4.596, -74.075, 0.02),
        "validar": ["candelaria"],
        "rechazar": ["droguer", "farmac", "hotel", "restaurante"],
    },
    {
        "nombre": "Chorro de Quevedo",
        "categoria": "Historia",
        "busquedas": ["Chorro de Quevedo, Bogotá"],
        "descripcion": "Esquina fundacional de Bogotá y hoy punto de encuentro con artistas, candeleros y cafés.",
        "direccion": "Calle 13 con Cra. 2",
        "ancla": (4.5955, -74.0755, 0.01),
        "validar": ["quevedo"],
        "rechazar": [],
    },
    {
        "nombre": "Museo Santa Clara",
        "categoria": "Cultura",
        "busquedas": ["Museo Santa Clara, Bogotá"],
        "descripcion": "Iglesia del siglo XVII convertida en museo de arte religioso, junto al Palacio de Nariño.",
        "direccion": "Cra. 7 #11-94",
        "ancla": (4.599, -74.077, 0.012),
        "validar": ["santa clara"],
        "rechazar": [],
    },
    {
        "nombre": "Cerro de Monserrate",
        "categoria": "Naturaleza",
        "busquedas": ["Monserrate, Bogotá", "Cerro de Monserrate"],
        "descripcion": "Santuario y mirador natural a 3.150 msnm con vista panorámica de la sabana.",
        "direccion": "Cerro de Monserrate",
        "ancla": (4.604, -74.056, 0.02),
        "validar": ["monserrate"],
        "rechazar": [],
    },
    {
        "nombre": "Parque Metropolitano Simon Bolivar",
        "categoria": "Naturaleza",
        "busquedas": [
            "Parque Metropolitano Simón Bolívar, Bogotá",
            "Parque Simón Bolívar, Bogotá",
        ],
        "descripcion": "El parque urbano más grande de la ciudad: lagos, vías ciclistas y la Ciudad Deportiva.",
        "direccion": "Cra. 54 #24-122",
        "ancla": (4.655, -74.085, 0.04),
        "validar": ["simón bolívar"],
        "rechazar": [],
    },
    {
        "nombre": "Jardin Botanico de Bogota",
        "categoria": "Naturaleza",
        "busquedas": [
            "Jardín Botánico José Celestino Mutis, Bogotá",
            "Jardín Botánico de Bogotá",
            "Jardin Botanico de Bogota",
        ],
        "descripcion": "14 hectáreas con colección de flora andina, orquideómico y jardines temáticos.",
        "direccion": "Av. 11 #68D-44",
        "ancla": (4.670, -74.097, 0.04),
        "validar": ["botánico", "botanico"],
        "rechazar": ["estación", "transmilenio", "cámara", "camara"],
    },
    {
        "nombre": "Quebrada La Vieja",
        "categoria": "Naturaleza",
        "busquedas": ["Quebrada La Vieja, Bogotá"],
        "descripcion": "Sendero en los Cerros Orientales con naciente de agua, fauna y flora de bosque andino.",
        "direccion": "Cerros Orientales",
        "ancla": (4.63, -74.04, 0.06),
        "validar": ["quebrada la vieja"],
        "rechazar": [],
    },
    {
        "nombre": "Complejo Recreativo El Salitre",
        "categoria": "Deporte",
        "busquedas": [
            "Parque de la Salud El Salitre, Bogotá",
            "Complejo Recreativo Deportivo El Salitre",
            "El Salitre, Bogotá",
        ],
        "descripcion": "Complejo deportivo distrital con piscinas olímpicas, canchas y áreas recreativas.",
        "direccion": "Cra. 57 con Calle 63",
        "ancla": (4.665, -74.085, 0.035),
        "validar": ["salitre"],
        "rechazar": ["transmilenio", "estación"],
    },
    {
        "nombre": "Estadio Nemesio Camacho El Campin",
        "categoria": "Deporte",
        "busquedas": ["Estadio Nemesio Camacho El Campín", "Estadio El Campín"],
        "descripcion": "Estadio mayor de Bogotá, sede de Millonarios y de grandes conciertos.",
        "direccion": "Cra. 30 #77-68",
        "ancla": (4.646, -74.078, 0.02),
        "validar": ["campín", "campin"],
        "rechazar": [],
    },
    {
        "nombre": "Salitre Magico",
        "categoria": "Entretenimiento",
        "busquedas": ["Salitre Mágico, Bogotá", "Parque Salitre Mágico"],
        "descripcion": "Parque de diversiones con montañas rusas y atracciones para toda la familia.",
        "direccion": "Cra. 68 con Calle 64",
        "ancla": (4.668, -74.091, 0.03),
        "validar": ["salitre mágico", "salitre magico"],
        "rechazar": ["estación", "transmilenio"],
    },
    {
        "nombre": "Centro Comercial Unicentro",
        "categoria": "Comercial",
        "busquedas": ["Centro Comercial Unicentro, Bogotá"],
        "descripcion": "Gran centro comercial del noroccidente de la ciudad, en la Calle 127.",
        "direccion": "Cra. 19 #109-60",
        "ancla": (4.700, -74.042, 0.03),
        "validar": ["unicentro"],
        "rechazar": [],
    },
    {
        "nombre": "Plaza de Usaquen",
        "categoria": "Gastronomia",
        "busquedas": ["Plaza de Usaquén, Bogotá"],
        "descripcion": "Plaza colonial con restaurantes, antiguas y el famoso flea market los domingos.",
        "direccion": "Calle 116 #7-50",
        "ancla": (4.695, -74.031, 0.02),
        "validar": ["usaquén"],
        "rechazar": [],
    },
    {
        "nombre": "Parque de la 93",
        "categoria": "Gastronomia",
        "busquedas": ["Parque de la 93, Bogotá"],
        "descripcion": "Área peatonal rodeada de restaurantes, cafeterías y zonas verdes.",
        "direccion": "Calle 93B #11-81",
        "ancla": (4.677, -74.048, 0.02),
        "validar": ["parque de la 93"],
        "rechazar": [],
    },
    {
        "nombre": "Zona T",
        "categoria": "Entretenimiento",
        "busquedas": ["Zona T, Bogotá", "Zona T, Chapinero", "Zona T, Bogotá D.C."],
        "descripcion": "Distrito de vida nocturna, restaurantes y bares entre la Calle 82 y la 85.",
        "direccion": "Zona T, Chapinero",
        "ancla": (4.668, -74.053, 0.03),
        "validar": ["zona t", "zona rosa"],
        "rechazar": ["camacho", "andino"],
    },
    {
        "nombre": "Centro Comercial Andino",
        "categoria": "Comercial",
        "busquedas": ["Centro Comercial Andino, Bogotá"],
        "descripcion": "Centro comercial de lujo en plena Calle 82.",
        "direccion": "Cra. 11 #82-100",
        "ancla": (4.670, -74.047, 0.03),
        "validar": ["andino"],
        "rechazar": [],
    },
    {
        "nombre": "Centro Comercial Calima",
        "categoria": "Comercial",
        "busquedas": [
            "Centro Comercial Calima, Bogotá",
            "CC Calima, Bogotá",
            "Calima, Bogotá D.C.",
        ],
        "descripcion": "Uno de los centros comerciales más antiguos de la ciudad, en la Cra 13 con Calle 37.",
        "direccion": "Cra. 13 #37-97",
        "ancla": (4.635, -74.077, 0.03),
        "validar": ["calima"],
        "rechazar": ["mallplaza", "nqs", "valle"],
    },
    {
        "nombre": "Centro Comercial Calle 100",
        "categoria": "Comercial",
        "busquedas": [
            "Centro Comercial Calle 100, Bogotá",
            "C.C. Calle 100, Bogotá",
        ],
        "descripcion": "Zona comercial y gastronómica sobre la Calle 100, corredor financiero del norte.",
        "direccion": "Calle 100 #70-40",
        "ancla": (4.678, -74.055, 0.03),
        "validar": ["calle 100"],
        "rechazar": ["transmilenio", "estación", "floresta", "suba"],
    },
    {
        "nombre": "Universidad Nacional de Colombia",
        "categoria": "Educacion",
        "busquedas": [
            "Universidad Nacional de Colombia, Bogotá",
            "Sede Central Bogotá Universidad Nacional",
        ],
        "descripcion": "Campus central de 1910 con arquitectura republicana, teatro, estadio y zonas verdes.",
        "direccion": "Cra. 45 #26-85",
        "ancla": (4.638, -74.087, 0.05),
        "validar": ["universidad nacional"],
        "rechazar": ["medellín", "sede acevedo"],
    },
    {
        "nombre": "Universidad de los Andes",
        "categoria": "Educacion",
        "busquedas": ["Universidad de los Andes, Bogotá"],
        "descripcion": "Universidad privada en el centro histórico, junto a la Plaza de Bolívar.",
        "direccion": "Calle 21 #15-20",
        "ancla": (4.601, -74.066, 0.02),
        "validar": ["universidad de los andes"],
        "rechazar": [],
    },
    {
        "nombre": "Aeropuerto Internacional El Dorado",
        "categoria": "Transporte",
        "busquedas": ["Aeropuerto Internacional El Dorado"],
        "descripcion": "Principal aeropuerto de Colombia y hub de conexión de América Latina.",
        "direccion": "Av. El Dorado",
        "ancla": (4.702, -74.148, 0.02),
        "validar": ["el dorado"],
        "rechazar": [],
    },
    {
        "nombre": "Terminal de Transportes Salitre",
        "categoria": "Transporte",
        "busquedas": [
            "Terminal de Transportes Salitre, Bogotá",
            "Estación de Transporte Salitre, Bogotá",
            "Terminal Salitre, Bogotá",
        ],
        "descripcion": "Terminal de transporte intermunicipal del noroccidente de Bogotá.",
        "direccion": "Cra. 43 #71-91",
        "ancla": (4.660, -74.100, 0.045),
        "validar": ["salitre"],
        "rechazar": ["punto de carga", "transmilenio", "estación de"],
    },
    # ------------------------------------------------------------------
    # Ola 2: mas instituciones educativas, hospitales, centros comerciales
    #        y parques/plazas de otras localidades (no solo centro/norte).
    # ------------------------------------------------------------------
    # --- Educacion -----------------------------------------------------
    {
        "nombre": "Universidad Distrital Francisco José de Caldas",
        "categoria": "Educacion",
        "busquedas": [
            "Universidad Distrital Francisco José de Caldas, Bogotá",
            "Facultad de Ingeniería Universidad Distrital, Bogotá",
            "Universidad Distrital, Bogotá",
        ],
        "descripcion": (
            "Universidad pública de Bogotá con sedes en Cra. 40 (ingeniería) y "
            "en La Candelaria (humanidades y pedagogía)."
        ),
        "direccion": "Cra. 40 #44-52",
        "ancla": (4.650, -74.067, 0.04),
        "validar": ["distrital"],
        "rechazar": ["medellín", "medellin", "cartagena", "barranquilla"],
        "destacado": True,
    },
    {
        "nombre": "Pontificia Universidad Javeriana",
        "categoria": "Educacion",
        "busquedas": ["Pontificia Universidad Javeriana, Bogotá"],
        "descripcion": (
            "Universidad jesuita fundada en 1623, campus histórico en la Cra. 7 "
            "entre la Calle 40 y la 42."
        ),
        "direccion": "Cra. 7 #40-62",
        "ancla": (4.624, -74.064, 0.02),
        "validar": ["javeriana"],
        # OJO: nunca usar "cali" como subcadena: aparece dentro de "localidad".
        "rechazar": ["javeriana, cali", "javeriana de cali", "villavicencio"],
        "destacado": True,
    },
    {
        "nombre": "Universidad del Rosario",
        "categoria": "Educacion",
        "busquedas": ["Universidad del Rosario, Bogotá"],
        "descripcion": (
            "Universidad fundada en 1653, la más antigua de Colombia, en pleno "
            "centro histórico junto a la Plaza del Chorro."
        ),
        "direccion": "Cra. 6 #12-72",
        "ancla": (4.602, -74.066, 0.03),
        "validar": ["del rosario"],
        "rechazar": ["ibagué", "ibague", "barranquilla"],
        "destacado": True,
    },
    {
        "nombre": "Universidad Externado de Colombia",
        "categoria": "Educacion",
        "busquedas": ["Universidad Externado de Colombia, Bogotá"],
        "descripcion": (
            "Universidad fundada en 1886 por Nicanor de Olguín, tradición en "
            "derecho, economía y ciencias sociales."
        ),
        "direccion": "Cra. 9 #7-25",
        "ancla": (4.604, -74.067, 0.02),
        "validar": ["externado"],
        "rechazar": [],
        "destacado": True,
    },
    {
        "nombre": "Universidad EAN",
        "categoria": "Educacion",
        "busquedas": [
            "Universidad EAN, Bogotá",
            "EAN, Bogotá",
            "Escuela de Administración y Negocios, Bogotá",
        ],
        "descripcion": (
            "Universidad privada de administración y negocios (antigua Escuela "
            "de Administración y Negocios) en el centro de Bogotá."
        ),
        "direccion": "Cra. 11 #78-47",
        "ancla": (4.663, -74.055, 0.02),
        "validar": ["universidad ean", "ean,", "escuela de administración"],
        "rechazar": [],
        "destacado": True,
    },
    {
        "nombre": "Universidad La Salle",
        "categoria": "Educacion",
        "busquedas": ["Universidad La Salle, Bogotá"],
        "descripcion": (
            "Universidad privada de tradición católica en la Cra. 5 con la "
            "Calle 71, campus con grandes zonas verdes."
        ),
        "direccion": "Cra. 5 #71-51",
        "ancla": (4.655, -74.060, 0.03),
        "validar": ["la salle"],
        "rechazar": ["quito", "montreal", "angeles", "neuquén"],
        "destacado": True,
    },
    {
        "nombre": "Universidad Pedagógica Nacional",
        "categoria": "Educacion",
        "busquedas": ["Universidad Pedagógica Nacional, Bogotá"],
        "descripcion": (
            "Universidad pública dedicada a la formación de docentes, en el "
            "centro histórico de La Candelaria."
        ),
        "direccion": "Cra. 9 #45-67",
        "ancla": (4.615, -74.067, 0.05),
        "validar": ["pedagógica", "pedagogica"],
        "rechazar": [],
        "destacado": True,
    },
    # --- Salud ---------------------------------------------------------
    {
        "nombre": "Hospital San Ignacio",
        "categoria": "Salud",
        "busquedas": [
            "Hospital Universitario San Ignacio, Bogotá",
            "Hospital San Ignacio, Bogotá",
        ],
        "descripcion": (
            "Hospital universitario de alta complejidad de la Provincia de la "
            "Compañía de Jesús, en la Cra. 4 con la Calle 91."
        ),
        "direccion": "Calle 41",
        "ancla": (4.629, -74.066, 0.02),
        "validar": ["san ignacio"],
        "rechazar": ["universidad", "clinica", "clínica"],
    },
    {
        "nombre": "Fundación Santa Fe de Bogotá",
        "categoria": "Salud",
        "busquedas": [
            "Fundación Santa Fe de Bogotá",
            "Hospital de la Fundación Santa Fe de Bogotá",
        ],
        "descripcion": (
            "Centro médico privado de alta complejidad en la Calle 119, con "
            "hospital, consultorios e investigación."
        ),
        "direccion": "Calle 119 #9-9",
        "ancla": (4.695, -74.057, 0.03),
        "validar": ["santa fe"],
        "rechazar": ["argentina", "méxico", "mexico", "nebraska", "antioquia"],
    },
    {
        "nombre": "Hospital Militar Central",
        "categoria": "Salud",
        "busquedas": [
            "Hospital Militar Central, Bogotá",
            "Centro Médico Militar General Gardella, Bogotá",
        ],
        "descripcion": (
            "Hospital de la Fuerzas Militares (CGM), alta complejidad, en la "
            "Cra. 37 con la Calle 21."
        ),
        "direccion": "Cra. 37 #21-31",
        "ancla": (4.649, -74.066, 0.03),
        "validar": ["militar"],
        "rechazar": [],
    },
    {
        "nombre": "Hospital El Tunal",
        "categoria": "Salud",
        "busquedas": ["Hospital El Tunal, Bogotá"],
        "descripcion": (
            "Hospital público de segundo y tercer nivel en el sur de la ciudad "
            "(localidad de Tunjuelito), junto al Parque El Tunal."
        ),
        "direccion": "Cra. 24 #55-37",
        "ancla": (4.601, -74.104, 0.03),
        "validar": ["hospital"],
        "rechazar": ["parque", "biblioteca", "complejo"],
    },
    # --- Centros comerciales (otras localidades) ------------------------
    {
        "nombre": "Centro Comercial Titán Plaza",
        "categoria": "Comercial",
        "busquedas": ["Centro Comercial Titán Plaza, Bogotá", "Titán Plaza, Bogotá"],
        "descripcion": "Centro comercial del sur de la ciudad, en la Calle 17 con la Cra. 104 (Bosa).",
        "direccion": "Cra. 70C #86-30",
        "ancla": (4.695, -74.086, 0.03),
        "validar": ["titán plaza", "titan plaza", "titán", "titan"],
        "rechazar": [],
    },
    {
        "nombre": "Centro Comercial Bima",
        "categoria": "Comercial",
        "busquedas": ["Centro Comercial Bima, Bogotá", "Bima, Bogotá"],
        "descripcion": "Centro comercial de la localidad de Suba, sobre la Cra. 45.",
        "direccion": "Cra. 45, Suba",
        "ancla": (4.807, -74.039, 0.02),
        "validar": ["bima"],
        "rechazar": [],
    },
    {
        "nombre": "Centro Comercial Plaza de las Américas",
        "categoria": "Comercial",
        "busquedas": [
            "Centro Comercial Plaza de las Américas, Bogotá",
            "Plaza de las Américas, Bogotá",
        ],
        "descripcion": "Gran centro comercial del suroccidente, sobre la Cra. 71D en Hipotecho (Puente Aranda).",
        "direccion": "Cra. 71D #6S-94",
        "ancla": (4.630, -74.133, 0.035),
        "validar": ["américas", "americas"],
        "rechazar": ["houston", "san antonio", "puerto rico"],
    },
    {
        "nombre": "Centro Comercial Plaza Central",
        "categoria": "Comercial",
        "busquedas": ["Centro Comercial Plaza Central, Bogotá", "Plaza Central, Bogotá"],
        "descripcion": "Centro comercial y de esparcimiento sobre la Cra. 65, en la localidad de Puente Aranda.",
        "direccion": "Cra. 65, Puente Aranda",
        "ancla": (4.632, -74.116, 0.03),
        "validar": ["plaza central"],
        "rechazar": ["transmilenio", "estación"],
    },
    # --- Parques y plazas de otras localidades ---------------------------
    {
        "nombre": "Parque Metropolitano El Tunal",
        "categoria": "Naturaleza",
        "busquedas": [
            "Complejo Recreativo Deportivo El Tunal, Bogotá",
            "Parque El Tunal, Bogotá",
            "El Tunal, Bogotá",
        ],
        "descripcion": (
            "Parque metropolitano de 118 hectáreas al sur de la ciudad "
            "(Tunjuelito/Usme): lagos, ciclovía, biblioteca y deporte."
        ),
        "direccion": "Cra. 24 #55-37",
        "ancla": (4.601, -74.104, 0.035),
        "validar": ["el tunal"],
        "rechazar": ["hospital", "biblioteca"],
    },
    {
        "nombre": "Hospital de Suba",
        "categoria": "Salud",
        "busquedas": ["Hospital de Suba, Bogotá", "Hospital Local de Suba, Bogotá"],
        "descripcion": (
            "Hospital local de la localidad de Suba, en el barrio Turingia, con "
            "urgencias y consultorios externos."
        ),
        "direccion": "Cra. 103B, Suba",
        "ancla": (4.753, -74.092, 0.03),
        "validar": ["hospital de suba"],
        "rechazar": ["clinica", "clínica"],
    },
    {
        "nombre": "Parque Río Bogotá",
        "categoria": "Naturaleza",
        "busquedas": ["Parque Río Bogotá, Bogotá", "Parque Río Bogotá"],
        "descripcion": (
            "Parque lineal sobre el río Bogotá en la localidad de Engativá, con "
            "ciclovía, canchas y zonas de recreación."
        ),
        "direccion": "Cra. 13, Engativá",
        "ancla": (4.727, -74.130, 0.035),
        "validar": [
            "líneal río bogotá",
            "lineal rio bogota",
            "parque río bogotá",
            "parque rio bogota",
        ],
        "rechazar": ["planta", "tratamiento"],
    },
    {
        "nombre": "Parque Independencia",
        "categoria": "Naturaleza",
        "busquedas": ["Parque Independencia, Bogotá"],
        "descripcion": (
            "Parque urbano del centro con el Museo de Arte Moderno, el "
            "Planetario y el Altar de la Patria."
        ),
        "direccion": "Cra. 7 #25-85",
        "ancla": (4.611, -74.069, 0.03),
        "validar": ["independencia"],
        "rechazar": ["museo"],
    },
    {
        "nombre": "Cementerio Central",
        "categoria": "Historia",
        "busquedas": ["Cementerio Central, Bogotá", "Cementerio Central de Bogotá"],
        "descripcion": (
            "Cementerio nacional de 1836 con panteones de próceres, mártires y "
            "figuras de la historia de Colombia (localidad de Los Mártires)."
        ),
        "direccion": "Cra. 19 #19-97",
        "ancla": (4.617, -74.076, 0.02),
        "validar": ["cementerio central"],
        "rechazar": ["norte"],
    },
    {
        "nombre": "Parque Público Vecinal Juan Amarillo",
        "categoria": "Naturaleza",
        "busquedas": [
            "Parque Público Vecinal Juan Amarillo, Bogotá",
            "Parque Juan Amarillo, Bogotá",
        ],
        "descripcion": (
            "Parque vecinal de la localidad de Engativá con canchas, áreas "
            "verdes y espacios recreativos para la comunidad."
        ),
        "direccion": "Engativá, Bogotá",
        "ancla": (4.729, -74.112, 0.03),
        "validar": ["juan amarillo"],
        "rechazar": ["humedal", "planta"],
    },
    {
        "nombre": "Barrio La Perseverancia",
        "categoria": "Historia",
        "busquedas": ["La Perseverancia, Bogotá"],
        "descripcion": (
            "Barrio obrero de 1928 al pie de los Cerros Orientales (localidad "
            "de Santa Fe), cuna de la Escuela Superior de Comercio."
        ),
        "direccion": "La Perseverancia, Bogotá",
        "ancla": (4.621, -74.054, 0.03),
        "validar": ["perseverancia"],
        "rechazar": ["avenida nueva", "zapatos", "peluquer"],
    },
    # --- Otros puntos destacados ----------------------------------------
    {
        "nombre": "Torre Colpatria",
        "categoria": "Historia",
        "busquedas": ["Torre Colpatria, Bogotá", "Edificio Colpatria, Bogotá"],
        "descripcion": (
            "Rascacielos de 1979 y edificio más emblemático del skyline de "
            "Bogotá; su mirador ofrece vistas de la sabana."
        ),
        "direccion": "Cra. 7 #11-52",
        "ancla": (4.6167, -74.0677, 0.015),
        "validar": ["colpatria"],
        "rechazar": [],
    },
    {
        "nombre": "Mercado de Paloquemao",
        "categoria": "Gastronomia",
        "busquedas": ["Mercado de Paloquemao, Bogotá", "Paloquemao, Bogotá"],
        "descripcion": (
            "Mayor mercado de abastos de Bogotá: frutas andinas, carnes, "
            "especias y pescados en la Cra. 22 con la Calle 41."
        ),
        "direccion": "Cra. 22 #41A-12",
        "ancla": (4.623, -74.093, 0.03),
        "validar": ["paloquemao"],
        "rechazar": ["transmilenio", "estación"],
    },
    {
        "nombre": "Casa Museo Fernando Botero",
        "categoria": "Cultura",
        "busquedas": [
            "Casa Museo Fernando Botero, Bogotá",
            "Museo Fernando Botero, Bogotá",
            "Museo Botero, Bogotá",
        ],
        "descripcion": (
            "Casa de 1969 donde vivió el maestro Fernando Botero, hoy museo "
            "con su colección personal en La Macarena."
        ),
        "direccion": "Cra. 4 #21-73",
        "ancla": (4.607, -74.070, 0.02),
        "validar": ["botero"],
        "rechazar": ["medellín", "medellin", "plaza"],
    },
    {
        "nombre": "Centro Cultural Gabriel García Márquez",
        "categoria": "Cultura",
        "busquedas": [
            "Centro Cultural Gabriel García Márquez, Bogotá",
            "Centro Cultural GGM, Bogotá",
        ],
        "descripcion": (
            "Casa del Autor de la FUNCIONP, con biblioteca, sala de lectura, "
            "cafetería y programación cultural gratuita."
        ),
        "direccion": "Av. Jiménez #5-71",
        "ancla": (4.603, -74.072, 0.03),
        "validar": ["gabriel garcía márquez", "gabriel garcia marquez", "ggm"],
        "rechazar": [],
    },
    {
        "nombre": "Museo de Bogotá",
        "categoria": "Cultura",
        "busquedas": ["Museo de Bogotá", "Museo de Bogotá, La Candelaria"],
        "descripcion": (
            "Museo de la historia de la ciudad: desde los muiscas hasta la "
            "Bogotá contemporánea, en el centro histórico."
        ),
        "direccion": "Cra. 7 #11-82",
        "ancla": (4.601, -74.076, 0.03),
        "validar": ["museo de bogotá", "museo de bogota"],
        "rechazar": ["universidad", "biblioteca"],
    },
    # --- Mas universidades verificadas ---------------------------------
    {
        "nombre": "Universidad Sergio Arboleda",
        "categoria": "Educacion",
        "busquedas": ["Universidad Sergio Arboleda, Bogotá"],
        "descripcion": (
            "Universidad privada de tradición humanística con campus propio en "
            "la Calle 74, entre el Parque de la 93 y la Zona T."
        ),
        "direccion": "Calle 74 #11-51",
        "ancla": (4.661, -74.060, 0.02),
        "validar": ["sergio arboleda"],
        "rechazar": [],
        "destacado": True,
    },
    {
        "nombre": "Universidad Militar Nueva Granada",
        "categoria": "Educacion",
        "busquedas": ["Universidad Militar Nueva Granada, Bogotá"],
        "descripcion": (
            "Universidad pública de las Fuerzas Militares con campus en la "
            "Cra. 11, entre Usaquén y el norte de Chapinero."
        ),
        "direccion": "Cra. 11 #101-80",
        "ancla": (4.683, -74.043, 0.02),
        "validar": ["militar nueva granada"],
        "rechazar": [],
        "destacado": True,
    },
    {
        "nombre": "Universidad El Bosque",
        "categoria": "Educacion",
        "busquedas": ["Universidad El Bosque, Bogotá"],
        "descripcion": (
            "Universidad privada de ciencias de la salud en la Av. Calle 134 "
            "de la localidad de Usaquén."
        ),
        "direccion": "Calle 134 #13-20",
        "ancla": (4.711, -74.032, 0.02),
        "validar": ["el bosque"],
        "rechazar": [],
        "destacado": True,
    },
    {
        "nombre": "Clínica del Country",
        "categoria": "Salud",
        "busquedas": ["Clínica del Country, Bogotá"],
        "descripcion": (
            "Centro médico privado de alta complejidad en la Cra. 16 con la "
            "Calle 79, cerca del Parque de la 93."
        ),
        "direccion": "Cra. 16 #79B-50",
        "ancla": (4.669, -74.056, 0.02),
        "validar": ["del country", "country"],
        "rechazar": ["universidad"],
    },
]


def _get(url: str, params: dict) -> list | dict:
    req = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def dentro_de_bogota(lat: float, lon: float) -> bool:
    left, top, right, bottom = BOGOTA_VIEWBOX
    return left <= lon <= right and bottom <= lat <= top


def geocode(sitio: dict, cache: dict) -> dict:
    validar = [v.lower() for v in sitio.get("validar", [])]
    rechazar = [r.lower() for r in sitio.get("rechazar", [])]
    lat_ok, lon_ok, tol = sitio["ancla"]

    def candidatos_de(query: str) -> list[dict]:
        """Cachea la lista COMPLETA de candidatos (limit=5), no solo el primero.

        Asi la validacion puede descartar el primer resultado (por ejemplo una
        drogueria o el homonimo de otra localidad) y usar el siguiente.
        """
        clave = f"v3:{query.strip().lower()}"
        if clave in cache:
            return cache[clave]

        time.sleep(1.1)  # politica de uso de Nominatim: 1 consulta/segundo
        data = _get(
            NOMINATIM,
            {
                "q": query,
                "format": "jsonv2",
                "limit": 5,
                "countrycodes": "co",
                "viewbox": ",".join(str(v) for v in BOGOTA_VIEWBOX),
                "bounded": 1,
            },
        )
        nuevos = [
            {
                "lat": float(d["lat"]),
                "lon": float(d["lon"]),
                "display_name": d["display_name"],
            }
            for d in data
        ]
        if not nuevos:
            # Nominatim responde vacio de forma intermitente: usa la ultima
            # respuesta conocida (cache v2) si existe.
            previo = cache.get(f"v2:{query.strip().lower()}")
            if previo:
                nuevos = previo if isinstance(previo, list) else [previo]
        cache[clave] = nuevos
        save_cache(cache)
        return nuevos

    ultimo_error = "sin intentos"
    for query in sitio["busquedas"]:
        candidatos = candidatos_de(query)
        if not candidatos:
            ultimo_error = f"sin resultados para '{query}'"
            continue

        for loc in candidatos:
            nombre_res = loc["display_name"].lower()
            if not dentro_de_bogota(loc["lat"], loc["lon"]):
                ultimo_error = f"fuera de Bogota: {loc['display_name']}"
                continue
            if validar and not any(v in nombre_res for v in validar):
                ultimo_error = f"nombre no coincide ({loc['display_name']})"
                continue
            if any(r in nombre_res for r in rechazar):
                ultimo_error = f"resultado descartado ({loc['display_name']})"
                continue
            if abs(loc["lat"] - lat_ok) > tol or abs(loc["lon"] - lon_ok) > tol:
                ultimo_error = (
                    f"lejos del anchor ({loc['lat']}, {loc['lon']}): {loc['display_name']}"
                )
                continue
            return loc

    raise RuntimeError(ultimo_error)


def reverse(lat: float, lon: float, cache: dict) -> str | None:
    key = f"rev:{lat:.6f},{lon:.6f}"
    if key in cache:
        return cache[key]
    time.sleep(1.1)
    data = _get(NOMINATIM_REVERSE, {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 18})
    calle = None
    if isinstance(data, dict):
        parte = data.get("address", {})
        calle = parte.get("pedestrian") or parte.get("footway") or parte.get("road")
    cache[key] = calle
    save_cache(cache)
    return calle


def sql_quote(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


# Sitios marcados manualmente como destacados (mas alla de las categorias).
DESTACADOS_MANUALES = {"Plaza de Bolivar", "Cerro de Monserrate"}


def sitio_destacado(sitio: dict) -> bool:
    """¿El sitio debe guardarse con ``destacado = TRUE``?

    Criterio: las instituciones educativas (nuevas y existentes) mas los
    hitos señalados en ``DESTACADOS_MANUALES``.
    """
    if sitio.get("destacado"):
        return True
    return sitio["categoria"] == "Educacion" or sitio["nombre"] in DESTACADOS_MANUALES


def main() -> None:
    cache = load_cache()
    rows, fallos = [], []
    for i, sitio in enumerate(SITIOS, 1):
        try:
            loc = geocode(sitio, cache)
        except Exception as exc:  # noqa: BLE001
            fallos.append((sitio["nombre"], str(exc)))
            continue
        calle = reverse(loc["lat"], loc["lon"], cache)
        rows.append((sitio, calle, loc))
        print(
            f"[{i:02d}/{len(SITIOS)}] {sitio['nombre']}: {loc['lat']}, {loc['lon']}"
            f" | {loc['display_name'][:75]} | calle: {calle}"
        )

    if fallos:
        print("\nSitios sin geocodificar:")
        for nombre, err in fallos:
            print(f"  - {nombre}: {err}")

    inserts = []
    for sitio, calle, loc in rows:
        direccion = calle or sitio["direccion"]
        ref = f"{sitio['direccion']} | OSM: {loc['display_name']}"
        inserts.append(
            "    ({}, {}, {}, {}, {}, {}, ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326))".format(
                sql_quote(sitio["nombre"]),
                sql_quote(sitio["categoria"]),
                sql_quote(sitio["descripcion"]),
                sql_quote(direccion),
                sql_quote(ref),
                "TRUE" if sitio_destacado(sitio) else "FALSE",
                lat=loc["lat"],
                lon=loc["lon"],
            )
        )

    sql = f"""-- Archivo generado por db/geocode_seed.py (no editar a mano)
-- Sitios de interes de Bogota D.C. geocodificados desde OpenStreetMap/Nominatim.
-- Se ejecuta automaticamente la primera vez que se levanta el contenedor PostGIS.
-- Columna geom: geometry(Point, SRID 4326) con indice GIST.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS sitios_interes (
    id            SERIAL PRIMARY KEY,
    nombre        TEXT NOT NULL,
    categoria     TEXT NOT NULL,
    descripcion   TEXT,
    direccion     TEXT,
    ref_ubicacion TEXT,
    destacado     BOOLEAN NOT NULL DEFAULT FALSE,
    geom          geometry(Point, 4326) NOT NULL,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Migracion idempotente para esquemas creados antes de la columna `destacado`.
ALTER TABLE sitios_interes ADD COLUMN IF NOT EXISTS destacado BOOLEAN NOT NULL DEFAULT FALSE;

-- Indices
-- GIST: alimenta ST_DWithin, ST_Distance y el operador &&
CREATE INDEX IF NOT EXISTS idx_sitios_interes_geom ON sitios_interes USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_sitios_categoria ON sitios_interes (categoria);
-- Habilita el ON CONFLICT (nombre) del seed incremental de abajo.
CREATE UNIQUE INDEX IF NOT EXISTS uq_sitios_interes_nombre ON sitios_interes (nombre);

-- Seed INCREMENTAL: solo inserta los sitios que aun no existen (idempotente
-- ante reinicios del contenedor y ante nuevas ediciones de la lista).
INSERT INTO sitios_interes (nombre, categoria, descripcion, direccion, ref_ubicacion, destacado, geom) VALUES
{{values}}
ON CONFLICT (nombre) DO NOTHING;

-- Verificacion del tipo geometrico y del indice GIST
-- (para columnas PostGIS, information_schema.reporta 'USER-DEFINED',
--  por eso se consulta la vista geometry_columns y pg_indexes)
DO $$
DECLARE
    v_tipo   text;
    v_srid   int;
    v_indice text;
BEGIN
    SELECT type, srid INTO v_tipo, v_srid
      FROM geometry_columns
     WHERE f_table_name = 'sitios_interes' AND f_geometry_column = 'geom';

    IF v_tipo IS NULL OR upper(v_tipo) <> 'POINT' OR v_srid <> 4326 THEN
        RAISE EXCEPTION 'geom debe ser geometry(Point, 4326); encontrado: % / srid %',
                        v_tipo, v_srid;
    END IF;

    SELECT indexname INTO v_indice
      FROM pg_indexes
     WHERE tablename = 'sitios_interes'
       AND indexdef ILIKE '%USING gist%(%geom%)';

    IF v_indice IS NULL THEN
        RAISE EXCEPTION 'Falta el indice GIST sobre geom';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'sitios_interes' AND column_name = 'destacado'
    ) THEN
        RAISE EXCEPTION 'Falta la columna destacado';
    END IF;

    RAISE NOTICE 'OK: geom geometry(Point,4326) con indice GIST %', v_indice;
END $$;
"""
    sql = sql.replace("{values}", ",\n".join(inserts))
    (OUT_DIR / "init.sql").write_text(sql, encoding="utf-8")
    (OUT_DIR / "seed.json").write_text(
        json.dumps(
            [
                {
                    "nombre": s["nombre"],
                    "categoria": s["categoria"],
                    "descripcion": s["descripcion"],
                    "direccion": calle or s["direccion"],
                    "ref_ubicacion": loc["display_name"],
                    "destacado": sitio_destacado(s),
                    "lat": loc["lat"],
                    "lon": loc["lon"],
                }
                for s, calle, loc in rows
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nOK: {len(rows)}/{len(SITIOS)} sitios -> db/init.sql y db/seed.json")


if __name__ == "__main__":
    main()
