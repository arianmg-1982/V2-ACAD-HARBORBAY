import csv
import json
import os
import logging
from collections import defaultdict
from datetime import datetime

# --- CONFIGURACION GENERAL ---
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
# Archivos de entrada normalizados
APARTAMENTOS_CSV = os.path.join(SCRIPT_DIR, "apartamentos.csv")
SWITCHES_CSV = os.path.join(SCRIPT_DIR, "switches.csv")
TIPOS_APARTAMENTO_CSV = os.path.join(SCRIPT_DIR, "tipos_apartamento.csv")
# Archivos de salida
LISP_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "dibujo_red.lsp")
BOM_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "bom_proyecto.txt")
LOG_FILE = os.path.join(SCRIPT_DIR, "logs.TXT")
ENCODING = "utf-8"

# --- CONFIGURACION DE LOGS ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
# Limpiar handlers existentes para evitar duplicados
if root_logger.hasHandlers():
    root_logger.handlers.clear()
file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding=ENCODING)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)
root_logger.addHandler(console_handler)


def cargar_configuracion():
    """Carga el archivo de configuración JSON."""
    try:
        with open(CONFIG_FILE, 'r', encoding=ENCODING) as f:
            logging.info(f"Cargando configuración desde '{CONFIG_FILE}'...")
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Error crítico: El archivo de configuración '{CONFIG_FILE}' no fue encontrado.")
        raise
    except json.JSONDecodeError:
        logging.error(f"Error crítico: El archivo '{CONFIG_FILE}' no es un JSON válido.")
        raise

def cargar_datos_normalizados():
    """
    Carga y procesa los datos desde los archivos CSV normalizados para construir
    la estructura de datos que necesita el resto del script.
    """
    logging.info("Cargando datos desde archivos CSV normalizados...")

    # 1. Cargar la definición de tipos de apartamento
    try:
        with open(TIPOS_APARTAMENTO_CSV, mode='r', encoding=ENCODING) as f:
            reader = csv.DictReader(f)
            tipos_apartamento = {row['tipo']: row for row in reader}
    except FileNotFoundError:
        logging.error(f"Error crítico: No se encontró el archivo '{TIPOS_APARTAMENTO_CSV}'.")
        raise

    # Inicializar la estructura de datos principal
    torres = defaultdict(lambda: {
        "nombre": "",
        "niveles": defaultdict(lambda: defaultdict(int)),
        "switches": {},
    })

    # 2. Cargar la configuración de switches
    try:
        with open(SWITCHES_CSV, mode='r', encoding=ENCODING) as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                torre_id = i
                torres[torre_id]['nombre'] = row['torre_nombre']
                torres[torre_id]['switches'] = {
                    'SW-WIFI': row['modelo_wifi'],
                    'SW-TEL': row['modelo_tel'],
                    'SW-IPTV': row['modelo_iptv'],
                    'SW-CCTV': row['modelo_cctv'],
                    'SW-DATA': row['modelo_data'],
                }
    except FileNotFoundError:
        logging.error(f"Error crítico: No se encontró el archivo '{SWITCHES_CSV}'.")
        raise

    # Añadir MDF (Torre 0) manualmente
    torres[0]['nombre'] = 'MDF'
    torres[0]['switches'] = torres[1]['switches'].copy() # Asumimos que MDF tiene los mismos modelos que IDF1
    torres[0]['switches']['SW-UPS'] = 'UPS' # Añadir UPS solo al MDF


    # 3. Cargar apartamentos y agregar cantidades de dispositivos
    try:
        with open(APARTAMENTOS_CSV, mode='r', encoding=ENCODING) as f:
            reader = csv.DictReader(f)
            for row in reader:
                torre_id = int(row['torre_nombre'].replace('IDF', ''))
                nivel_id = int(row['nivel_nombre'].replace('NIVEL', ''))
                tipo_apt = row['tipo_apartamento']

                # Obtener la configuración de dispositivos para este tipo de apto
                config_apt = tipos_apartamento.get(tipo_apt)
                if not config_apt:
                    logging.warning(f"Tipo de apartamento '{tipo_apt}' no encontrado en {TIPOS_APARTAMENTO_CSV}. Saltando fila.")
                    continue

                # Incrementar contadores de dispositivos para esa torre/nivel
                torres[torre_id]['niveles'][nivel_id]['apQty'] += int(config_apt['ap'])
                torres[torre_id]['niveles'][nivel_id]['telQty'] += int(config_apt['telefono'])
                torres[torre_id]['niveles'][nivel_id]['tvQty'] += int(config_apt['tv'])
                # Mantener camQty y datQty en 0 como en el original
                torres[torre_id]['niveles'][nivel_id]['camQty'] = 0
                torres[torre_id]['niveles'][nivel_id]['datQty'] = 0
                torres[torre_id]['niveles'][nivel_id]['nivel_nombre'] = row['nivel_nombre']


    except FileNotFoundError:
        logging.error(f"Error crítico: No se encontró el archivo '{APARTAMENTOS_CSV}'.")
        raise

    # Convertir a lista ordenada por ID de torre
    torres_list = [value for key, value in sorted(torres.items())]
    logging.info(f"Cargados y procesados datos para {len(torres_list)} torres.")
    return torres_list

# --- El resto de las funciones de dibujo (sin cambios) ---

def lisp_escribir(f, comando):
    """Escribe una línea en el archivo LISP con salto de línea."""
    f.write(comando + "\n")

def lisp_crear_capa(f, nombre, color):
    """Genera el comando LISP para crear una capa de forma robusta."""
    nombre_escaped = nombre.replace('"', '\\"')
    lisp_escribir(f, f'(command "-LAYER" "N" "{nombre_escaped}" "C" "{color}" "" "")')

def lisp_seleccionar_capa_y_color(f, capa, color):
    """Genera comandos para seleccionar capa y color."""
    lisp_escribir(f, f'(command "-LAYER" "S" "{capa}" "")')
    lisp_escribir(f, f'(command "-COLOR" "{color}")')

def lisp_dibujar_linea(f, p1, p2):
    """Dibuja una línea en LISP."""
    lisp_escribir(f, f'(command "_.LINE" (list {p1[0]} {p1[1]}) (list {p2[0]} {p2[1]}) "")')

def lisp_dibujar_texto(f, punto, altura, texto, justificacion="C", capa="Textos", color=7):
    """Dibuja texto en LISP de forma no interactiva."""
    texto_escaped = texto.replace('"', '\\"')
    lisp_seleccionar_capa_y_color(f, capa, color)
    lisp_escribir(f, f'(command "-TEXT" "S" "Standard" "J" "{justificacion}" (list {punto[0]} {punto[1]}) {altura} 0 "{texto_escaped}")')

def lisp_dibujar_rectangulo(f, p1, p2):
    """Dibuja un rectángulo usando PLINE para máxima compatibilidad."""
    (x1, y1) = p1
    (x2, y2) = p2
    lisp_dibujar_polilinea(f, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], cerrada=True)

def lisp_dibujar_circulo(f, centro, radio):
    """Dibuja un círculo en LISP."""
    lisp_escribir(f, f'(command "_.CIRCLE" (list {centro[0]} {centro[1]}) {radio})')

def lisp_dibujar_polilinea(f, puntos, cerrada=False):
    """Dibuja una polilínea."""
    comando = '(command "_.PLINE"'
    for p in puntos:
        comando += f' (list {p[0]} {p[1]})'
    if cerrada:
        comando += ' "C")'
    else:
        comando += ' "")'
    lisp_escribir(f, comando)

def lisp_dibujar_hatch(f):
    """Rellena el último objeto creado de forma segura."""
    lisp_escribir(f, '(command "-HATCH" "S" "L" "" "")')

def lisp_dibujar_arco_eliptico(f, centro, eje_x, eje_y, angulo_inicio, angulo_fin):
    """Dibuja un arco elíptico."""
    lisp_escribir(f, f'(command "_.ELLIPSE" "A" (list {centro[0]} {centro[1]}) (list {eje_x[0]} {eje_x[1]}) (list {eje_y[0]} {eje_y[1]}) {angulo_inicio} {angulo_fin})')

def dibujar_icono_ap(f, cfg, x, y):
    capa_info = cfg['CAPAS']['APs']
    lisp_seleccionar_capa_y_color(f, "APs", capa_info)
    base = 20
    altura = 25
    p1 = (x - base / 2, y)
    p2 = (x + base / 2, y)
    p3 = (x, y + altura)
    lisp_dibujar_polilinea(f, [p1, p2, p3, p1])
    centro_circulos = (x, y + altura)
    radios = [10, 21.25, 30]
    for radio in radios:
        lisp_dibujar_circulo(f, centro_circulos, radio)

def dibujar_icono_telefono(f, cfg, x, y):
    capa_info = cfg['CAPAS']['Telefonos']
    lisp_seleccionar_capa_y_color(f, "Telefonos", capa_info)
    cuerpo_ancho, cuerpo_alto = 20, 30
    auricular_radio = 5
    p1 = (x - cuerpo_ancho / 2, y)
    p2 = (x + cuerpo_ancho / 2, y + cuerpo_alto)
    lisp_dibujar_rectangulo(f, p1, p2)
    lisp_dibujar_circulo(f, (x, y + cuerpo_alto + auricular_radio + 2), auricular_radio)

def dibujar_icono_tv(f, cfg, x, y):
    capa_info = cfg['CAPAS']['TVs']
    lisp_seleccionar_capa_y_color(f, "TVs", capa_info)
    pantalla_ancho, pantalla_alto = 40, 25
    p1_pantalla = (x - pantalla_ancho / 2, y)
    p2_pantalla = (x + pantalla_ancho / 2, y + pantalla_alto)
    lisp_dibujar_rectangulo(f, p1_pantalla, p2_pantalla)
    soporte_base = 20
    p1_soporte = (x - soporte_base / 2, y)
    p2_soporte = (x + soporte_base / 2, y)
    p3_soporte = (x, y - 10)
    lisp_dibujar_polilinea(f, [p1_soporte, p2_soporte, p3_soporte, p1_soporte])

def dibujar_icono_camara(f, cfg, x, y):
    capa_info = cfg['CAPAS']['Camaras']
    lisp_seleccionar_capa_y_color(f, "Camaras", capa_info)
    caja_ancho, caja_alto = 20, 15
    p1 = (x - caja_ancho / 2, y)
    p2 = (x + caja_ancho / 2, y + caja_alto)
    lisp_dibujar_rectangulo(f, p1, p2)
    lisp_dibujar_circulo(f, (x, y + caja_alto / 2), 3)

def dibujar_icono_dato(f, cfg, x, y):
    capa_info = cfg['CAPAS']['Datos']
    lisp_seleccionar_capa_y_color(f, "Datos", capa_info)
    base = 20
    altura = 20
    p1 = (x - base / 2, y)
    p2 = (x + base / 2, y)
    p3 = (x, y + altura)
    lisp_dibujar_polilinea(f, [p1, p2, p3], cerrada=True)
    lisp_dibujar_hatch(f)

def dibujar_switch(f, cfg, x, y, nombre, modelo):
    ancho, alto = cfg['SWITCH_ANCHO'], cfg['SWITCH_ALTO']
    lisp_seleccionar_capa_y_color(f, "Switches", cfg['CAPAS']['Switches'])
    p1 = (x, y)
    p2 = (x + ancho, y + alto)
    lisp_dibujar_rectangulo(f, p1, p2)
    texto_completo = f"{nombre} ({modelo})" if modelo else nombre
    x_centro_texto = x + ancho / 2
    y_centro_texto = y + alto / 2
    lisp_dibujar_texto(f, (x_centro_texto, y_centro_texto), cfg['SWITCH_TEXTO_ALTURA'], texto_completo, justificacion="MC")

def dibujar_ups(f, cfg, x, y):
    ancho, alto = cfg['UPS_ANCHO'], cfg['UPS_ALTO']
    lisp_seleccionar_capa_y_color(f, "UPS", cfg['CAPAS']['UPS'])
    p1 = (x, y)
    p2 = (x + ancho, y + alto)
    lisp_dibujar_rectangulo(f, p1, p2)
    lisp_dibujar_texto(f, (x + 25, y + 25), 15, "UPS")
    lisp_dibujar_texto(f, (x + 5, y - 20), 10, "ALIMENTACION")

def dibujar_cableado_utp(f, cfg, torres, coords, alturas_niveles):
    lisp_escribir(f, "\n; === DIBUJAR CABLES UTP ===")
    lisp_escribir(f, '(princ "\\nDibujando cables UTP...")')
    device_draw_order = ["apQty", "telQty", "tvQty"]
    for torre in torres:
        torre_id = torre['id']
        if not torre.get('switches'): continue
        max_y_dispositivo = 0
        for nivel_id, nivel_data in torre['niveles'].items():
            y_dispositivo_nivel = alturas_niveles[nivel_id] + cfg['DISPOSITIVO_Y_OFFSET']
            for tipo_qty in device_draw_order:
                if nivel_data.get(tipo_qty, 0) > 0:
                    y_dispositivo_nivel += cfg['DISPOSITIVO_ESPACIADO_Y']
            max_y_dispositivo = max(max_y_dispositivo, y_dispositivo_nivel)

        y_troncal_base = max_y_dispositivo + 50
        offset_y_troncal = 0
        for tipo_qty in device_draw_order:
            lisp_seleccionar_capa_y_color(f, "Cables_UTP", 5)
            conf_disp = cfg['DISPOSITIVOS'].get(tipo_qty)
            if not conf_disp: continue
            sw_tipo_mapeado = cfg['MAPEO_SWITCH'].get(tipo_qty)
            if not sw_tipo_mapeado or sw_tipo_mapeado not in coords[torre_id]['switches']: continue
            niveles_con_dispositivo = [nid for nid, nivel in torre['niveles'].items() if nivel.get(tipo_qty, 0) > 0]
            if not niveles_con_dispositivo: continue

            sw_coords = coords[torre_id]['switches'][sw_tipo_mapeado]
            p_sw_lado = (sw_coords[0] + cfg['SWITCH_ANCHO'] / 2, sw_coords[1] + cfg['SWITCH_ALTO'])

            y_troncal = y_troncal_base + offset_y_troncal
            p1 = (p_sw_lado[0], p_sw_lado[1] + 10)
            p2 = (p_sw_lado[0], y_troncal)
            lisp_dibujar_polilinea(f, [p_sw_lado, p1, p2])

            x_max_dispositivo = max(coords[torre_id][f'disp_{nid}_{conf_disp["label"]}'][0] for nid in niveles_con_dispositivo)
            lisp_dibujar_linea(f, p2, (x_max_dispositivo, y_troncal))

            for nivel_id in niveles_con_dispositivo:
                p_disp = coords[torre_id][f'disp_{nivel_id}_{conf_disp["label"]}']
                p_troncal_nivel = (p_disp[0], y_troncal)
                lisp_dibujar_linea(f, p_troncal_nivel, p_disp)
            offset_y_troncal += 30
    lisp_escribir(f, '(princ "DONE.")')

def dibujar_cableado_fibra(f, cfg, torres, coords):
    """Dibuja el cableado de fibra óptica con líneas diagonales directas desde el MDF a cada IDF."""
    lisp_escribir(f, "\n; === DIBUJAR CABLES DE FIBRA OPTICA (DIAGONAL) ===")
    lisp_escribir(f, '(princ "\\nDibujando cables de Fibra Optica...")')
    lisp_seleccionar_capa_y_color(f, "Fibra_Data", 2)  # Color cian para fibra

    mdf_torre = torres[0]
    idfs = [t for t in torres if t['id'] != 0]

    # Itera sobre los tipos de switch que necesitan fibra (todos menos UPS)
    sw_tipos_fibra = [sw for sw in cfg.get('SWITCH_DRAW_ORDER', []) if sw != 'SW-UPS']

    for sw_tipo in sw_tipos_fibra:
        # Verifica si el switch existe en el MDF
        if sw_tipo not in mdf_torre['switches'] or sw_tipo not in coords[0]['switches']:
            continue

        # Punto de partida desde el switch del MDF
        p_mdf_sw_base = coords[0]['switches'][sw_tipo]
        # Salir desde el lado derecho del switch del MDF
        p_start_mdf = (p_mdf_sw_base[0] + cfg['SWITCH_ANCHO'], p_mdf_sw_base[1] + cfg['SWITCH_ALTO'] / 2)

        # Itera sobre cada torre IDF para conectar la fibra
        for idf in idfs:
            # Verifica si la torre IDF tiene este tipo de switch
            if sw_tipo not in idf['switches'] or sw_tipo not in coords[idf['id']]['switches']:
                continue

            # Punto de llegada en el switch del IDF
            p_idf_sw_base = coords[idf['id']]['switches'][sw_tipo]
            # Llegar al lado izquierdo del switch del IDF
            p_final_idf = (p_idf_sw_base[0], p_idf_sw_base[1] + cfg['SWITCH_ALTO'] / 2)

            # Dibuja la línea diagonal directa
            lisp_dibujar_linea(f, p_start_mdf, p_final_idf)

            # Calcula el punto medio para la etiqueta
            label_x = (p_start_mdf[0] + p_final_idf[0]) / 2
            label_y = (p_start_mdf[1] + p_final_idf[1]) / 2
            label_text = f"FO {sw_tipo.replace('SW-', '')}"
            lisp_dibujar_texto(f, (label_x, label_y + 10), 10, label_text, "C", "Textos", 7)

    lisp_escribir(f, '(princ "DONE.")')


def dibujar_cableado_ups(f, cfg, torres, coords):
    """Dibuja el cableado de alimentación desde el UPS a cada switch con líneas diagonales directas."""
    lisp_escribir(f, "\n; === DIBUJAR ALIMENTACION DESDE UPS (DIAGONAL) ===")
    lisp_escribir(f, '(princ "\\nDibujando alimentacion desde UPS...")')
    lisp_seleccionar_capa_y_color(f, "UPS", 1)  # Color rojo para UPS

    # Verificar si el UPS existe
    if 'SW-UPS' not in coords[0]['switches']:
        logging.warning("No se encontraron coordenadas para el UPS (SW-UPS). No se dibujará el cableado de alimentación.")
        return

    # Punto de partida desde el centro inferior del UPS
    p_ups_base = coords[0]['switches']['SW-UPS']
    p_start_ups = (p_ups_base[0] + cfg['UPS_ANCHO'] / 2, p_ups_base[1])

    # Recorrer todas las torres y todos sus switches para alimentarlos
    for torre in torres:
        for sw_nombre in torre['switches']:
            # No conectar el UPS a sí mismo
            if sw_nombre == 'SW-UPS':
                continue

            # Verificar que el switch tiene coordenadas
            if sw_nombre not in coords[torre['id']]['switches']:
                continue

            # Punto de llegada en el centro inferior del switch
            p_sw_base = coords[torre['id']]['switches'][sw_nombre]
            p_conexion_sw = (p_sw_base[0] + cfg['SWITCH_ANCHO'] / 2, p_sw_base[1])

            # Dibujar la línea diagonal directa
            lisp_dibujar_linea(f, p_start_ups, p_conexion_sw)

            # Calcular punto medio para la etiqueta
            label_x = (p_start_ups[0] + p_conexion_sw[0]) / 2
            label_y = (p_start_ups[1] + p_conexion_sw[1]) / 2
            label_text = f"UPS-PWR"
            lisp_dibujar_texto(f, (label_x, label_y + 10), 10, label_text, "C", "Textos", 7)

    lisp_escribir(f, '(princ "DONE.")')

def generar_lisp(cfg, torres):
    with open(LISP_OUTPUT_FILE, "w", encoding=ENCODING) as f:
        logging.info(f"Generando archivo LISP: '{LISP_OUTPUT_FILE}'...")
        lisp_escribir(f, '(setq *error* (lambda (msg) (if msg (princ (strcat "\\nError: " msg)))))')
        lisp_escribir(f, '(setvar "OSMODE" 0)')
        lisp_escribir(f, '(command "_.UNDO" "BEGIN")')

        for nombre, color in cfg['CAPAS'].items():
            lisp_crear_capa(f, nombre, color)

        coords = defaultdict(dict)
        x_torre_actual = cfg['X_INICIAL']
        for i, torre in enumerate(torres):
            torre['id'] = i
            torre['x'] = x_torre_actual
            x_torre_actual += cfg['LONGITUD_PISO'] + cfg['SEPARACION_ENTRE_TORRES']

        # 1. Calcular la altura necesaria para cada nivel
        alturas_calculadas = defaultdict(float)
        # Altura del sótano
        sotano_height = cfg['UPS_ALTO'] + cfg.get('UPS_SWITCH_GAP', 30)
        sotano_height += (cfg['SWITCH_ALTO'] + cfg['SWITCH_VERTICAL_SPACING']) * len(cfg.get('SWITCH_DRAW_ORDER', []))
        alturas_calculadas[0] = sotano_height + 100 # Espacio extra

        # Altura de otros niveles
        all_niveles_ids = sorted(list(set(nid for t in torres for nid in t['niveles'] if nid != 0)))
        for nivel_id in all_niveles_ids:
            num_device_types = sum(1 for t in torres if t['niveles'].get(nivel_id, {}).get('apQty', 0) > 0)
            alturas_calculadas[nivel_id] = (num_device_types * cfg['DISPOSITIVO_ESPACIADO_Y']) + cfg['ESPACIO_ENTRE_NIVELES']

        # 2. Asignar coordenadas Y a cada nivel
        alturas_niveles = {0: cfg['Y_INICIAL']}
        y_nivel_actual = cfg['Y_INICIAL']
        for nivel_id in sorted(alturas_calculadas.keys()):
            if nivel_id == 0: continue
            y_nivel_actual += alturas_calculadas[nivel_id - 1] if (nivel_id -1) in alturas_calculadas else cfg['ESPACIO_ENTRE_NIVELES']
            alturas_niveles[nivel_id] = y_nivel_actual

        # 3. Dibujar
        for torre in torres:
            torre_id = torre['id']
            x_base = torre['x']
            lisp_escribir(f, f'\n; === DIBUJAR TORRE: {torre["nombre"]} ===')
            lisp_dibujar_texto(f, (x_base, cfg['Y_INICIAL'] + 50), cfg['TORRE_LABEL_ALTURA'], torre['nombre'])

            # Dibujar Sótano
            y_sotano_base = alturas_niveles[0]
            x_pos = x_base + 50
            y_cursor = y_sotano_base + 50
            coords[torre_id]['switches'] = {}

            if 'SW-UPS' in torre['switches'] and torre_id == 0:
                dibujar_ups(f, cfg, x_pos, y_cursor)
                coords[torre_id]['switches']['SW-UPS'] = (x_pos, y_cursor)
                y_cursor += cfg['UPS_ALTO'] + cfg.get('UPS_SWITCH_GAP', 30)

            draw_order = cfg.get('SWITCH_DRAW_ORDER', [])
            for item_nombre in draw_order:
                if item_nombre in torre['switches']:
                    dibujar_switch(f, cfg, x_pos, y_cursor, item_nombre, torre['switches'][item_nombre])
                    coords[torre_id]['switches'][item_nombre] = (x_pos, y_cursor)
                    y_cursor += cfg['SWITCH_ALTO'] + cfg['SWITCH_VERTICAL_SPACING']

            # Dibujar otros niveles
            for nivel_id, nivel_data in sorted(torre['niveles'].items()):
                if nivel_id == 0: continue
                y_nivel = alturas_niveles[nivel_id]
                x_dispositivo = x_base + 150
                y_dispositivo_cursor = y_nivel + cfg['DISPOSITIVO_Y_OFFSET']
                device_draw_order = ["apQty", "telQty", "tvQty"]
                for tipo_qty in device_draw_order:
                    conf = cfg['DISPOSITIVOS'][tipo_qty]
                    cantidad = nivel_data.get(tipo_qty, 0)
                    if cantidad > 0:
                        globals()[f"dibujar_icono_{conf['icono']}"](f, cfg, x_dispositivo, y_dispositivo_cursor)
                        lisp_dibujar_texto(f, (x_dispositivo - 30, y_dispositivo_cursor + 15), 10, f"{cantidad}x{conf['label']}", "C")
                        coords[torre_id][f'disp_{nivel_id}_{conf["label"]}'] = (x_dispositivo, y_dispositivo_cursor)
                        y_dispositivo_cursor += cfg['DISPOSITIVO_ESPACIADO_Y']

        lisp_escribir(f, "\n; === DIBUJAR LÍNEAS DE NIVEL ===")
        x_start_nivel, x_end_nivel = cfg['X_INICIAL'] - 50, torres[-1]['x'] + cfg['LONGITUD_PISO'] + 50
        for nivel_id, y_nivel in alturas_niveles.items():
            lisp_seleccionar_capa_y_color(f, "Niveles", cfg['CAPAS']['Niveles'])
            lisp_dibujar_linea(f, (x_start_nivel, y_nivel), (x_end_nivel, y_nivel))
            nivel_nombre = "SOTANO" if nivel_id == 0 else f"NIVEL {nivel_id}"
            lisp_dibujar_texto(f, (x_start_nivel + 10, y_nivel + 10), 15, nivel_nombre, "L")

        # Dibujar Cableado
        dibujar_cableado_utp(f, cfg, torres, coords, alturas_niveles)
        dibujar_cableado_fibra(f, cfg, torres, coords)
        dibujar_cableado_ups(f, cfg, torres, coords)

        lisp_escribir(f, "\n; === FINALIZAR DIBUJO ===")
        lisp_escribir(f, '(command "_.ZOOM" "E")')
        lisp_escribir(f, '(command "_.UNDO" "END")')
        logging.info(f"Archivo LISP '{LISP_OUTPUT_FILE}' generado con éxito.")

def main():
    try:
        logging.info("--- INICIO DEL PROCESO DE GENERACIÓN DE PLANOS ---")
        config = cargar_configuracion()
        datos_torres = cargar_datos_normalizados()
        if not datos_torres:
            logging.warning("No se encontraron datos de torres para procesar.")
            return
        generar_lisp(config, datos_torres)
        logging.info("--- PROCESO COMPLETADO EXITOSAMENTE ---")
    except Exception as e:
        logging.critical(f"Ha ocurrido un error inesperado: {e}", exc_info=True)

if __name__ == "__main__":
    main()
