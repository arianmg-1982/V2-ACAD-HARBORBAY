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
    device_draw_order = ["apQty", "telQty", "tvQty", "datQty", "camQty"]
    for torre in torres:
        torre_id = torre['id']
        if not torre.get('switches'): continue
        max_x_dispositivo = 0
        for nivel_id, nivel_data in torre['niveles'].items():
            x_dispositivo_nivel = torre['x'] + 150
            for tipo_qty in device_draw_order:
                if nivel_data.get(tipo_qty, 0) > 0:
                    x_dispositivo_nivel += cfg['DISPOSITIVO_ESPACIADO_X']
            max_x_dispositivo = max(max_x_dispositivo, x_dispositivo_nivel)
        x_troncal_base = max_x_dispositivo + 50
        offset_troncal_x = 0
        for tipo_qty in device_draw_order:
            lisp_seleccionar_capa_y_color(f, "Cables_UTP", 5)
            conf_disp = cfg['DISPOSITIVOS'].get(tipo_qty)
            if not conf_disp: continue
            sw_tipo_mapeado = cfg['MAPEO_SWITCH'].get(tipo_qty)
            if not sw_tipo_mapeado or sw_tipo_mapeado not in coords[torre_id]['switches']: continue
            niveles_con_dispositivo = [nid for nid, nivel in torre['niveles'].items() if nivel.get(tipo_qty, 0) > 0]
            if not niveles_con_dispositivo: continue
            total_cables = sum(torre['niveles'][nid].get(tipo_qty, 0) for nid in niveles_con_dispositivo)
            if total_cables > 0 and torre_id == 0:
                label_total_text = f"{total_cables}xCAT6A"
                sw_coords = coords[torre_id]['switches'][sw_tipo_mapeado]
                p_sw_lado = (sw_coords[0] + cfg['SWITCH_ANCHO'], sw_coords[1] + cfg['SWITCH_ALTO'] / 2)
                label_total_pos = (p_sw_lado[0] + 15, p_sw_lado[1])
                lisp_dibujar_texto(f, label_total_pos, 10, label_total_text, "C", "Textos", 7)
            sw_coords = coords[torre_id]['switches'][sw_tipo_mapeado]
            p_sw_lado = (sw_coords[0] + cfg['SWITCH_ANCHO'], sw_coords[1] + cfg['SWITCH_ALTO'] / 2)
            x_troncal = x_troncal_base + offset_troncal_x
            p1 = (p_sw_lado[0] + 10, p_sw_lado[1])
            p2 = (x_troncal, p_sw_lado[1])
            lisp_dibujar_polilinea(f, [p_sw_lado, p1, p2])
            y_max_dispositivo = max(coords[torre_id][f'disp_{nid}_{conf_disp["label"]}'][1] for nid in niveles_con_dispositivo)
            lisp_dibujar_linea(f, p2, (x_troncal, y_max_dispositivo))
            for nivel_id in niveles_con_dispositivo:
                p_disp = coords[torre_id][f'disp_{nivel_id}_{conf_disp["label"]}']
                p_troncal_nivel = (x_troncal, p_disp[1])
                p_final_disp = (p_disp[0] + cfg['DISPOSITIVO_ANCHO']/2, p_disp[1])
                lisp_dibujar_linea(f, p_troncal_nivel, p_final_disp)
            offset_troncal_x += 30
    lisp_escribir(f, '(princ "DONE.")')

def dibujar_cableado_fibra(f, cfg, torres, coords):
    lisp_escribir(f, "\n; === DIBUJAR CABLES DE FIBRA OPTICA ===")
    lisp_escribir(f, '(princ "\\nDibujando cables de Fibra Optica...")')
    lisp_seleccionar_capa_y_color(f, "Fibra_Data", 2)
    mdf_torre = torres[0]
    idfs = [t for t in torres if t['id'] != 0]
    # Ajuste para bajar las líneas de fibra óptica
    y_bandeja_start = coords[0]['switches']['SW-UPS'][1] - cfg['UPS_ALTO'] - 80 - 200
    y_offset = 0
    sw_tipos_fibra = [sw for sw in cfg['SWITCH_DRAW_ORDER'] if sw != 'SW-UPS']
    for sw_tipo in sw_tipos_fibra:
        if sw_tipo not in mdf_torre['switches']: continue
        idfs_con_switch = [idf for idf in idfs if sw_tipo in idf['switches']]
        if not idfs_con_switch: continue
        y_bandeja = y_bandeja_start - y_offset
        p_mdf_sw = coords[0]['switches'][sw_tipo]
        p_start_mdf = (p_mdf_sw[0] + cfg['SWITCH_ANCHO'], p_mdf_sw[1] + cfg['SWITCH_ALTO'] / 2)
        p_despegue_mdf = (p_start_mdf[0] + 20, p_start_mdf[1])
        p_bajada_mdf = (p_despegue_mdf[0] + 20, y_bandeja)
        lisp_dibujar_polilinea(f, [p_start_mdf, p_despegue_mdf, p_bajada_mdf])
        punto_anterior = p_bajada_mdf
        fibras_restantes = len(idfs_con_switch)
        for idf in idfs_con_switch:
            p_idf_sw = coords[idf['id']]['switches'][sw_tipo]
            p_subida_idf = (p_idf_sw[0] - 20, y_bandeja)
            p_entrada_idf = (p_idf_sw[0], p_subida_idf[1] + 20)
            p_final_idf = (p_idf_sw[0], p_idf_sw[1] + cfg['SWITCH_ALTO'] / 2)
            lisp_dibujar_linea(f, punto_anterior, p_subida_idf)
            label_text = f"{fibras_restantes}xFO {sw_tipo.replace('SW-', '')}"
            label_x = (punto_anterior[0] + p_subida_idf[0]) / 2
            lisp_dibujar_texto(f, (label_x, y_bandeja + 10), 10, label_text, "C", "Textos", 7)
            lisp_dibujar_polilinea(f, [p_subida_idf, p_entrada_idf, p_final_idf])
            punto_anterior = p_subida_idf
            fibras_restantes -= 1
        y_offset += 40
    lisp_escribir(f, '(princ "DONE.")')

def dibujar_cableado_ups(f, cfg, torres, coords):
    lisp_escribir(f, '(princ "\\nDibujando alimentacion desde UPS...")')
    lisp_seleccionar_capa_y_color(f, "UPS", 1)
    if 'SW-UPS' not in coords[0]['switches']: return
    p_ups = coords[0]['switches']['SW-UPS']
    y_bandeja_ups = p_ups[1] - cfg['UPS_ALTO'] - 40
    p_start_ups = (p_ups[0] + cfg['UPS_ANCHO'] / 2, p_ups[1])
    p_bajada_ups = (p_start_ups[0], y_bandeja_ups)
    lisp_dibujar_linea(f, p_start_ups, p_bajada_ups)
    punto_anterior = p_bajada_ups
    switches_a_alimentar = []
    for t in torres:
        for sw_nombre in t['switches']:
            if sw_nombre != 'SW-UPS':
                switches_a_alimentar.append({'torre_id': t['id'], 'sw_nombre': sw_nombre})
    cables_restantes = len(switches_a_alimentar)
    switches_a_alimentar.sort(key=lambda item: coords[item['torre_id']]['switches'][item['sw_nombre']][0])
    for item in switches_a_alimentar:
        p_sw = coords[item['torre_id']]['switches'][item['sw_nombre']]
        p_conexion_sw = (p_sw[0] + cfg['SWITCH_ANCHO'] / 2, p_sw[1])
        p_subida_sw = (p_conexion_sw[0], y_bandeja_ups)
        lisp_dibujar_linea(f, punto_anterior, p_subida_sw)
        label_text = f"{cables_restantes}xUPS-PWR"
        label_x = (punto_anterior[0] + p_subida_sw[0]) / 2
        lisp_dibujar_texto(f, (label_x, y_bandeja_ups + 10), 10, label_text, "C", "Textos", 7)
        lisp_dibujar_linea(f, p_subida_sw, p_conexion_sw)
        punto_anterior = p_subida_sw
        cables_restantes -= 1
    lisp_escribir(f, '(princ "DONE.")')

def generar_lisp(cfg, torres):
    with open(LISP_OUTPUT_FILE, "w", encoding=ENCODING) as f:
        logging.info(f"Iniciando la generación del archivo LISP: '{LISP_OUTPUT_FILE}'...")
        lisp_escribir(f, '(setq *error* (lambda (msg) (if msg (princ (strcat "\\nError: " msg)))))')
        lisp_escribir(f, '(setvar "OSMODE" 0)')
        lisp_escribir(f, '(command "_.-PURGE" "ALL" "*" "N")')
        lisp_escribir(f, '(command "_.REGEN")')
        lisp_escribir(f, '(command "VISUALSTYLE" "Wireframe")')
        lisp_escribir(f, '(command "_.UNDO" "BEGIN")')
        lisp_escribir(f, '(princ "--- INICIO DE DIBUJO AUTOMATIZADO HARBORBAY ---")')
        lisp_escribir(f, "\n; === CREAR CAPAS ===")
        lisp_escribir(f, '(princ "\\nCreando capas...")')
        for nombre, color in cfg['CAPAS'].items():
            lisp_crear_capa(f, nombre, color)
        lisp_escribir(f, '(princ "DONE.")')
        coords = defaultdict(dict)
        x_torre_actual = cfg['X_INICIAL']
        for i, torre in enumerate(torres):
            torre['id'] = i
            torre['x'] = x_torre_actual
            x_torre_actual += cfg['LONGITUD_PISO'] + cfg['SEPARACION_ENTRE_TORRES']
        y_nivel_actual = cfg['Y_INICIAL']
        alturas_niveles = {}
        niveles_ordenados = sorted(list(set(n_id for t in torres for n_id in t['niveles'])))
        device_keys = cfg['DISPOSITIVOS'].keys()
        for nivel_id in niveles_ordenados:
            alturas_niveles[nivel_id] = y_nivel_actual
            if nivel_id == 0 and any('switches' in t and t['switches'] for t in torres):
                 max_devices_in_level = sum(1 for key in device_keys if any(t['niveles'][0].get(key, 0) > 0 for t in torres if 0 in t['niveles']))
                 level_height = (max_devices_in_level * cfg.get('DISPOSITIVO_ESPACIADO_Y', 80)) + 200
            else:
                max_devices_in_level = 0
                for torre in torres:
                    if nivel_id in torre['niveles']:
                        num_devices = sum(1 for key in device_keys if torre['niveles'][nivel_id].get(key, 0) > 0)
                        max_devices_in_level = max(max_devices_in_level, num_devices)
                level_height = (max_devices_in_level * cfg.get('DISPOSITIVO_ESPACIADO_Y', 80)) + cfg['ESPACIO_ENTRE_NIVELES']
            y_nivel_actual += level_height
        for torre in torres:
            torre_id = torre['id']
            x_base = torre['x']
            lisp_escribir(f, f'\n; === DIBUJAR TORRE: {torre["nombre"]} ===')
            lisp_escribir(f, f'(princ "\\n>> Dibujando Torre: {torre["nombre"]}...")')
            y_etiqueta_torre = alturas_niveles.get(min(alturas_niveles.keys()), cfg['Y_INICIAL']) - cfg['TORRE_LABEL_OFFSET_Y']
            lisp_dibujar_texto(f, (x_base, y_etiqueta_torre), cfg['TORRE_LABEL_ALTURA'], torre['nombre'])
            lisp_escribir(f, '(princ "\\n   - Dibujando switches y UPS...")')
            y_sotano = alturas_niveles.get(0, cfg['Y_INICIAL'])
            x_pos = x_base + 50
            y_cursor = y_sotano - 50
            coords[torre_id]['switches'] = {}
            if 'SW-UPS' in torre['switches'] and torre_id == 0:
                y_cursor -= cfg['UPS_ALTO']
                dibujar_ups(f, cfg, x_pos, y_cursor)
                coords[torre_id]['switches']['SW-UPS'] = (x_pos, y_cursor)
                y_cursor -= cfg.get('UPS_SWITCH_GAP', 30)
            draw_order = cfg['SWITCH_DRAW_ORDER']
            items_a_dibujar = [item for item in draw_order if item in torre['switches'] and item != 'SW-UPS']
            for item_nombre in reversed(items_a_dibujar):
                y_cursor -= cfg['SWITCH_ALTO']
                dibujar_switch(f, cfg, x_pos, y_cursor, item_nombre, torre['switches'].get(item_nombre, ''))
                coords[torre_id]['switches'][item_nombre] = (x_pos, y_cursor)
                y_cursor -= cfg['SWITCH_VERTICAL_SPACING']
            lisp_escribir(f, '(princ "DONE.")')
            lisp_escribir(f, f'(princ "\\n   - Dibujando dispositivos por nivel...")')
            device_draw_order = ["apQty", "telQty", "tvQty", "datQty", "camQty"]
            for nivel_id, nivel_data in sorted(torre['niveles'].items()):
                y_nivel = alturas_niveles[nivel_id]
                x_dispositivo = x_base + 150
                y_dispositivo_cursor = y_nivel + cfg['DISPOSITIVO_Y_OFFSET']
                for tipo_qty in device_draw_order:
                    conf = cfg['DISPOSITIVOS'].get(tipo_qty)
                    if not conf: continue
                    cantidad = nivel_data.get(tipo_qty, 0)
                    if cantidad > 0:
                        globals()[f"dibujar_icono_{conf['icono']}"](f, cfg, x_dispositivo, y_dispositivo_cursor)
                        lisp_dibujar_texto(f, (x_dispositivo - 30, y_dispositivo_cursor + 15), 10, f"{cantidad}x{conf['label']}", "C")
                        coords[torre_id][f'disp_{nivel_id}_{conf["label"]}'] = (x_dispositivo, y_dispositivo_cursor)
                        y_dispositivo_cursor += cfg.get('DISPOSITIVO_ESPACIADO_Y', 80)
            lisp_escribir(f, '(princ "DONE.")')
        lisp_escribir(f, "\n; === DIBUJAR LÍNEAS DE NIVEL ===")
        lisp_escribir(f, '(princ "\\nDibujando lineas de Nivel...")')
        y_ups_bottom = coords[0]['switches']['SW-UPS'][1] - cfg['UPS_ALTO']/2 if 'SW-UPS' in coords.get(0, {}).get('switches', {}) else cfg['Y_INICIAL'] - 200
        for nivel_id, y_nivel in alturas_niveles.items():
            lisp_seleccionar_capa_y_color(f, "Niveles", cfg['CAPAS']['Niveles'])
            x_start_nivel = cfg['X_INICIAL'] - 50
            y_linea = y_nivel
            if nivel_id == 0: y_linea = y_ups_bottom - 50
            p1 = (x_start_nivel, y_linea)
            p2 = (torres[-1]['x'] + cfg['LONGITUD_PISO'] + 50, y_linea)
            lisp_dibujar_linea(f, p1, p2)
            nivel_nombre = next((t['niveles'][nivel_id]['nivel_nombre'] for t in torres if nivel_id in t['niveles']), f"NIVEL {nivel_id}")
            lisp_dibujar_texto(f, (p1[0] + 10, y_linea + 10), 15, nivel_nombre)
        lisp_escribir(f, '(princ "DONE.")')
        lisp_escribir(f, "\n; === DIBUJAR CABLES ===")
        dibujar_cableado_utp(f, cfg, torres, coords, alturas_niveles)
        dibujar_cableado_fibra(f, cfg, torres, coords)
        dibujar_cableado_ups(f, cfg, torres, coords)
        lisp_escribir(f, "\n; === FINALIZAR DIBUJO ===")
        lisp_escribir(f, '(princ "\\nFinalizando y haciendo zoom...")')
        lisp_escribir(f, '(command "_.ZOOM" "E")')
        lisp_escribir(f, '(command "_.UNDO" "END")')
        lisp_escribir(f, '(princ "\\n--- PROCESO DE DIBUJO COMPLETADO ---")')
        logging.info(f"Archivo LISP '{LISP_OUTPUT_FILE}' generado con éxito.")

def generar_bom(cfg, torres):
    """Genera el archivo de listado de materiales (BOM)."""
    with open(BOM_OUTPUT_FILE, "w", encoding=ENCODING) as f:
        logging.info(f"Iniciando la generación del BOM: '{BOM_OUTPUT_FILE}'...")
        totales = defaultdict(int)
        switches_totales = defaultdict(int)
        modelos_switches = defaultdict(lambda: defaultdict(int))
        for torre in torres:
            for nivel in torre['niveles'].values():
                for tipo_qty in cfg['DISPOSITIVOS']:
                    totales[tipo_qty] += nivel.get(tipo_qty, 0)
            for sw_nombre, sw_modelo in torre['switches'].items():
                switches_totales[sw_nombre] += 1
                if sw_modelo:
                    modelos_switches[sw_nombre][sw_modelo] += 1
        total_puntos_red = sum(totales.values())
        total_cable_utp = total_puntos_red * 15
        f.write("============================================================\n")
        f.write("      LISTADO DE MATERIALES (BOM) - PROYECTO HARBORBAY\n")
        f.write("============================================================\n")
        f.write(f"Fecha de Generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("--- RESUMEN DEL PROYECTO ---\n")
        f.write(f"Total de Torres (MDF+IDF): {len(torres)}\n")
        f.write(f"Total de Puntos de Red:    {total_puntos_red}\n\n")
        f.write("--- TOTAL DE DISPOSITIVOS ---\n")
        for tipo_qty, conf in cfg['DISPOSITIVOS'].items():
            f.write(f"- {conf['label']:<10}: {totales[tipo_qty]} unidades\n")
        f.write("\n")
        f.write("--- TOTAL DE SWITCHES POR TIPO Y MODELO ---\n")
        for sw_nombre, cantidad in sorted(switches_totales.items()):
            if 'UPS' in sw_nombre: continue
            f.write(f"- {sw_nombre:<15}: {cantidad} unidades\n")
            if sw_nombre in modelos_switches:
                for modelo, q in modelos_switches[sw_nombre].items():
                    f.write(f"    - Modelo: {modelo} ({q} uds)\n")
        f.write("\n")
        f.write("--- ESTIMACIÓN DE CABLEADO ---\n")
        f.write(f"- Cable UTP CAT6A: ~{total_cable_utp:,} metros\n")
        total_fibra = (len(torres) -1) * len(cfg.get('SWITCH_CONFIG', {})) * 50
        f.write(f"- Fibra Óptica:    ~{total_fibra:,} metros (estimación bruta)\n\n")
        f.write("--- OBSERVACIONES ---\n")
        f.write("- Las cantidades se basan en los archivos de entrada CSV.\n")
        f.write("- La longitud del cableado es una estimación y requiere verificación en sitio.\n")
        f.write("- Se incluye 1 UPS centralizada en el MDF.\n")
        f.write("============================================================\n")
    logging.info(f"Archivo BOM '{BOM_OUTPUT_FILE}' generado con éxito.")

def main():
    """Función principal para ejecutar el script."""
    try:
        logging.info("--- INICIO DEL PROCESO DE GENERACIÓN DE PLANOS ---")
        config = cargar_configuracion()
        datos_torres = cargar_datos_normalizados()

        if not datos_torres:
            logging.warning("No se encontraron datos de torres para procesar. Terminando ejecución.")
            return

        generar_lisp(config, datos_torres)
        generar_bom(config, datos_torres)

        logging.info("--- PROCESO COMPLETADO EXITOSAMENTE ---")

    except Exception as e:
        logging.critical(f"Ha ocurrido un error inesperado en la ejecución: {e}", exc_info=True)

if __name__ == "__main__":
    main()
