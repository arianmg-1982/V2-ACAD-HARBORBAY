import csv
import json
import os
import logging
from collections import defaultdict
from datetime import datetime

# --- CONFIGURACION GENERAL ---
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
CSV_INPUT_FILE = os.path.join(SCRIPT_DIR, "torres.csv")
LISP_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "dibujo_red.lsp")
BOM_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "bom_proyecto.txt")
LOG_FILE = os.path.join(SCRIPT_DIR, "logs.TXT")
ENCODING = "utf-8"

# --- CONFIGURACION DE LOGS ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Log a archivo
file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding=ENCODING)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

# Log a consola
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

def cargar_datos_csv():
    """Carga y procesa los datos desde el archivo CSV de forma robusta."""
    if not os.path.exists(CSV_INPUT_FILE):
        logging.error(f"Error crítico: El archivo de datos '{CSV_INPUT_FILE}' no fue encontrado.")
        raise FileNotFoundError(f"No se encontró {CSV_INPUT_FILE}")

    torres = defaultdict(lambda: {
        "nombre": "",
        "niveles": defaultdict(dict),
        "switches": {},
    })

    # Columnas que representan cantidades de dispositivos
    qty_columns = ['apQty', 'telQty', 'tvQty', 'camQty', 'datQty']

    # Mapeo de columnas de switch en el CSV a nombres de switch internos
    switch_column_map = {
        'switch_FIREWALL': 'SW-FIREWALL',
        'switch_CORE': 'SW-CORE',
        'switch_wifi': 'SW-WIFI',
        'switch_tel': 'SW-TEL',
        'switch_iptv': 'SW-IPTV',
        'switch_cctv': 'SW-CCTV',
        'switch_data': 'SW-DATA',
    }

    with open(CSV_INPUT_FILE, mode='r', encoding=ENCODING) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                torre_id = int(row['TORRE'])
                nivel_id = int(row['NIVEL'])

                torre = torres[torre_id]
                if not torre['nombre']: # Asignar nombre solo una vez
                    torre['nombre'] = row['torre_nombre']

                nivel_data = torre['niveles'][nivel_id]

                # Copiar todos los datos de la fila al diccionario de nivel
                for key, value in row.items():
                    nivel_data[key] = value

                # Convertir explícitamente las cantidades a enteros
                for col in qty_columns:
                    try:
                        nivel_data[col] = int(row.get(col) or 0)
                    except (ValueError, TypeError):
                        logging.warning(f"Valor no numérico para '{col}' en la fila {reader.line_num}. Se usará 0.")
                        nivel_data[col] = 0

                # Consolidar switches y modelos por torre de forma explícita
                for csv_col, sw_name in switch_column_map.items():
                    if (row.get(csv_col) or '0') != '0':
                        modelo_col = f"{csv_col}_modelo"
                        torre['switches'][sw_name] = row.get(modelo_col, '')

                # Replicar el comportamiento original de tratar la UPS como un switch en los datos
                # para mantener la salida del dibujo sin cambios.
                if (row.get('switch_UPS') or '0') != '0':
                    torre['switches']['SW-UPS'] = row.get('switch_UPS_modelo', '')


            except (ValueError, KeyError) as e:
                logging.error(f"Error procesando fila del CSV: {row}. Error: {e}")
                continue

    # Convertir a lista ordenada por ID de torre
    torres_list = [value for key, value in sorted(torres.items())]
    logging.info(f"Cargados datos de {len(torres_list)} torres desde '{CSV_INPUT_FILE}'.")
    return torres_list

# --- FUNCIONES DE DIBUJO LISP ---

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

# --- FUNCIONES DE DIBUJO DE COMPONENTES ---

def dibujar_icono_ap(f, cfg, x, y):
    """Dibuja el icono de un AP: Triángulo con 3 círculos concéntricos."""
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
    """Dibuja el icono de un Teléfono: Rectángulo (cuerpo) + círculo (auricular)."""
    capa_info = cfg['CAPAS']['Telefonos']
    lisp_seleccionar_capa_y_color(f, "Telefonos", capa_info)

    cuerpo_ancho, cuerpo_alto = 20, 30
    auricular_radio = 5
    p1 = (x - cuerpo_ancho / 2, y)
    p2 = (x + cuerpo_ancho / 2, y + cuerpo_alto)
    lisp_dibujar_rectangulo(f, p1, p2)
    lisp_dibujar_circulo(f, (x, y + cuerpo_alto + auricular_radio + 2), auricular_radio)

def dibujar_icono_tv(f, cfg, x, y):
    """Dibuja el icono de una TV: Rectángulo (pantalla) + triángulo (soporte)."""
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
    """Dibuja el icono de una Cámara: Caja + arco elíptico."""
    capa_info = cfg['CAPAS']['Camaras']
    lisp_seleccionar_capa_y_color(f, "Camaras", capa_info)

    caja_ancho, caja_alto = 20, 15
    p1 = (x - caja_ancho / 2, y)
    p2 = (x + caja_ancho / 2, y + caja_alto)
    lisp_dibujar_rectangulo(f, p1, p2)
    # Simulación de lente
    lisp_dibujar_circulo(f, (x, y + caja_alto / 2), 3)

def dibujar_icono_dato(f, cfg, x, y):
    """Dibuja el icono de una Toma de Datos: Triángulo rojo relleno."""
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
    """Dibuja un switch con su etiqueta centrada dentro de la caja."""
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
    """Dibuja el icono de la UPS."""
    ancho, alto = cfg['UPS_ANCHO'], cfg['UPS_ALTO']
    lisp_seleccionar_capa_y_color(f, "UPS", cfg['CAPAS']['UPS'])
    p1 = (x, y)
    p2 = (x + ancho, y + alto)
    lisp_dibujar_rectangulo(f, p1, p2)
    lisp_dibujar_texto(f, (x + 25, y + 25), 15, "UPS")
    lisp_dibujar_texto(f, (x + 5, y - 20), 10, "ALIMENTACION")

# --- LÓGICA PRINCIPAL DE GENERACIÓN ---

def dibujar_cableado_utp(f, cfg, torres, coords, alturas_niveles):
    """Dibuja el cableado UTP desde los switches a los dispositivos con el nuevo enrutamiento."""
    lisp_escribir(f, "\n; === DIBUJAR CABLES UTP ===")
    lisp_escribir(f, '(princ "\\nDibujando cables UTP...")')
    lisp_seleccionar_capa_y_color(f, "Cables_UTP", cfg['CAPAS']['Cables_UTP'])

    device_draw_order = ["apQty", "telQty", "tvQty", "datQty", "camQty"]

    for torre in torres:
        torre_id = torre['id']
        if not torre.get('switches'):
            continue

        # Calcular el X máximo de los dispositivos en esta torre
        max_x_dispositivo = 0
        for nivel_id, nivel_data in torre['niveles'].items():
            x_dispositivo_nivel = torre['x'] + 150
            for tipo_qty in device_draw_order:
                if nivel_data.get(tipo_qty, 0) > 0:
                    x_dispositivo_nivel += cfg['DISPOSITIVO_ESPACIADO_X']
            max_x_dispositivo = max(max_x_dispositivo, x_dispositivo_nivel)

        x_troncal_base = max_x_dispositivo + 50 # Empezar troncales a la derecha del dispositivo más lejano

        offset_troncal_x = 0
        for tipo_qty in device_draw_order:
            conf_disp = cfg['DISPOSITIVOS'].get(tipo_qty)
            if not conf_disp: continue

            sw_tipo_mapeado = cfg['MAPEO_SWITCH'].get(tipo_qty)
            if not sw_tipo_mapeado or sw_tipo_mapeado not in coords[torre_id]['switches']:
                continue

            if not any(nivel.get(tipo_qty, 0) > 0 for nivel in torre['niveles'].values()):
                continue

            # Calcular el total de cables para este tipo de switch en esta torre
            total_cables = sum(nivel.get(tipo_qty, 0) for nivel in torre['niveles'].values())
            if total_cables > 0:
                label_total_text = f"{total_cables}xUTP"
                p_sw_lado = (coords[torre_id]['switches'][sw_tipo_mapeado][0] + cfg['SWITCH_ANCHO'] / 2, coords[torre_id]['switches'][sw_tipo_mapeado][1] - cfg['SWITCH_ALTO'] / 2)
                label_total_pos = (p_sw_lado[0] + 15, p_sw_lado[1] + 15)
                lisp_dibujar_texto(f, label_total_pos, 10, label_total_text, "Cables_UTP", cfg['CAPAS']['Cables_UTP'])

            p_sw_top = coords[torre_id]['switches'][sw_tipo_mapeado]
            p_sw_lado = (p_sw_top[0] + cfg['SWITCH_ANCHO'] / 2, p_sw_top[1] - cfg['SWITCH_ALTO'] / 2)

            p1 = (p_sw_lado[0] + 10, p_sw_lado[1])
            p2 = (p1[0] + 10, p1[1] + 10)

            x_troncal = x_troncal_base + offset_troncal_x
            p3_base = (x_troncal, p2[1])

            lisp_dibujar_polilinea(f, [p_sw_lado, p1, p2, p3_base])

            niveles_con_dispositivo = [nid for nid, nivel in torre['niveles'].items() if nivel.get(tipo_qty, 0) > 0]
            if not niveles_con_dispositivo: continue

            nivel_mas_alto_id = max(niveles_con_dispositivo)
            y_troncal_top = alturas_niveles[nivel_mas_alto_id] + cfg['DISPOSITIVO_Y_OFFSET']

            lisp_dibujar_linea(f, p3_base, (x_troncal, y_troncal_top))

            for nivel_id in niveles_con_dispositivo:
                p_disp = coords[torre_id][f'disp_{nivel_id}_{conf_disp["label"]}']

                p_troncal_nivel = (x_troncal, p_disp[1] - 20)
                p_debajo_disp = (p_disp[0] - 10, p_disp[1] - 20)
                p_final_disp = (p_disp[0] -10, p_disp[1])

                lisp_dibujar_polilinea(f, [p_troncal_nivel, p_debajo_disp, p_final_disp])
                lisp_dibujar_linea(f, p_final_disp, p_disp)

                cantidad = torre['niveles'][nivel_id].get(tipo_qty, 0)
                label_text = f"{cantidad}x{conf_disp['label']}"

                y_nivel_actual = alturas_niveles[nivel_id]
                y_nivel_anterior = alturas_niveles.get(nivel_id - 1, alturas_niveles.get(0, cfg['Y_INICIAL']))
                y_label = ((y_nivel_actual + y_nivel_anterior) / 2) + 10

                label_pos = (x_troncal + 15, y_label)
                lisp_dibujar_texto(f, label_pos, 10, label_text, "Cables_UTP", cfg['CAPAS']['Cables_UTP'])

            offset_troncal_x += 30

    lisp_escribir(f, '(princ "DONE.")')

def dibujar_cableado_fibra(f, cfg, torres, coords, alturas_niveles):
    """Dibuja el cableado de fibra óptica desde el MDF a los IDFs con el nuevo enrutamiento."""
    lisp_escribir(f, "\n; === DIBUJAR CABLES DE FIBRA OPTICA ===")
    lisp_escribir(f, '(princ "\\nDibujando cables de Fibra Optica...")')

    mdf_torre = torres[0]
    idfs = [t for t in torres if t['id'] != 0]

    y_ups = coords.get('ups_coord', (0, alturas_niveles[0] - 100))[1]
    y_bandeja_start = y_ups - 150 # Y inicial para las bandejas de fibra
    y_offset = 0

    # Obtener todos los tipos de switches que existen en los IDFs
    todos_sw_tipos_en_idfs = sorted(list(set(sw_tipo for idf in idfs for sw_tipo in idf['switches'] if sw_tipo in cfg['SWITCH_CONFIG'])))

    for sw_tipo in todos_sw_tipos_en_idfs:
        if sw_tipo not in mdf_torre['switches']:
            continue

        idfs_con_este_switch = [idf for idf in idfs if sw_tipo in idf['switches']]
        if not idfs_con_este_switch:
            continue

        sw_conf = cfg['SWITCH_CONFIG'].get(sw_tipo, {})
        lisp_seleccionar_capa_y_color(f, sw_conf.get('capa', 'Fibra'), sw_conf.get('color', 2))

        y_bandeja = y_bandeja_start - y_offset

        # Punto de inicio en el switch del MDF
        p_mdf_sw = coords[0]['switches'][sw_tipo]
        p_start_mdf = (p_mdf_sw[0], p_mdf_sw[1] - cfg['SWITCH_ALTO'] / 2)

        # Punto de bajada a la bandeja
        p_bajada_mdf = (p_start_mdf[0] + 50, y_bandeja)
        lisp_dibujar_linea(f, p_start_mdf, p_bajada_mdf)

        punto_anterior_horizontal = p_bajada_mdf
        fibras_restantes = len(idfs_con_este_switch)

        for idf in idfs_con_este_switch:
            p_idf_sw = coords[idf['id']]['switches'][sw_tipo]

            # Punto de subida desde la bandeja al IDF
            p_subida_idf = (p_idf_sw[0] - 50, y_bandeja)

            # Dibujar tramo horizontal
            lisp_dibujar_linea(f, punto_anterior_horizontal, p_subida_idf)

            # Dibujar etiqueta del tramo
            label_text = f"{fibras_restantes}xFO {sw_tipo.replace('SW-', '')}"
            label_x = (punto_anterior_horizontal[0] + p_subida_idf[0]) / 2
            lisp_dibujar_texto(f, (label_x, y_bandeja + 10), 10, label_text, sw_conf.get('capa', 'Fibra'), sw_conf.get('color', 2))

            # Dibujar diagonal de subida
            p_dest_idf = (p_idf_sw[0], p_idf_sw[1] - cfg['SWITCH_ALTO'] / 2)
            lisp_dibujar_linea(f, p_subida_idf, p_dest_idf)

            # Actualizar para el siguiente tramo
            punto_anterior_horizontal = p_subida_idf
            fibras_restantes -= 1

        y_offset += 40 # Espaciar verticalmente el siguiente tipo de fibra

    lisp_escribir(f, '(princ "DONE.")')

def generar_lisp(cfg, torres):
    """Función principal que genera el archivo LISP completo."""
    with open(LISP_OUTPUT_FILE, "w", encoding=ENCODING) as f:
        logging.info(f"Iniciando la generación del archivo LISP: '{LISP_OUTPUT_FILE}'...")

        # --- INICIALIZACIÓN DE AUTOCAD ---
        lisp_escribir(f, '(setq *error* (lambda (msg) (if msg (princ (strcat "\\nError: " msg)))))')
        lisp_escribir(f, '(setvar "OSMODE" 0)')
        lisp_escribir(f, '(command "_.-PURGE" "ALL" "*" "N")')
        lisp_escribir(f, '(command "_.REGEN")')
        lisp_escribir(f, '(command "VISUALSTYLE" "Wireframe")')
        lisp_escribir(f, '(command "_.UNDO" "BEGIN")')
        lisp_escribir(f, '(princ "--- INICIO DE DIBUJO AUTOMATIZADO HARBORBAY ---")')

        # --- CREACIÓN DE CAPAS ---
        lisp_escribir(f, "\n; === CREAR CAPAS ===")
        lisp_escribir(f, '(princ "\\nCreando capas...")')
        for nombre, color in cfg['CAPAS'].items():
            lisp_crear_capa(f, nombre, color)
        lisp_escribir(f, '(princ "DONE.")')

        # --- CÁLCULO DE POSICIONES Y ALMACENAMIENTO DE COORDENADAS ---
        coords = defaultdict(dict)

        # 1. Calcular coordenadas X para cada torre
        x_torre_actual = cfg['X_INICIAL']
        for i, torre in enumerate(torres):
            torre['id'] = i
            torre['x'] = x_torre_actual
            x_torre_actual += cfg['LONGITUD_PISO'] + cfg['SEPARACION_ENTRE_TORRES']

        # 2. Calcular coordenadas Y para cada nivel (dinámicamente)
        y_nivel_actual = cfg['Y_INICIAL']
        alturas_niveles = {}
        niveles_ordenados = sorted(list(set(n_id for t in torres for n_id in t['niveles'])))

        device_keys = cfg['DISPOSITIVOS'].keys()

        for nivel_id in niveles_ordenados:
            alturas_niveles[nivel_id] = y_nivel_actual

            max_devices_in_level = 0
            for torre in torres:
                if nivel_id in torre['niveles']:
                    num_devices = sum(1 for key in device_keys if torre['niveles'][nivel_id].get(key, 0) > 0)
                    max_devices_in_level = max(max_devices_in_level, num_devices)

            level_height = (max_devices_in_level * cfg.get('DISPOSITIVO_ESPACIADO_Y', 60)) + cfg['ESPACIO_ENTRE_NIVELES']
            y_nivel_actual += level_height

        # --- DIBUJAR TORRES, SWITCHES Y DISPOSITIVOS ---
        for torre in torres:
            torre_id = torre['id']
            x_base = torre['x']
            lisp_escribir(f, f'\n; === DIBUJAR TORRE: {torre["nombre"]} ===')
            lisp_escribir(f, f'(princ "\\n>> Dibujando Torre: {torre["nombre"]}...")')

            y_etiqueta_torre = alturas_niveles[min(alturas_niveles.keys())] - cfg['TORRE_LABEL_OFFSET_Y']
            lisp_dibujar_texto(f, (x_base, y_etiqueta_torre), cfg['TORRE_LABEL_ALTURA'], torre['nombre'])

            # Dibujar Switches y UPS en el Sótano
            lisp_escribir(f, '(princ "\\n   - Dibujando switches y UPS...")')
            y_sotano = alturas_niveles.get(0, cfg['Y_INICIAL'])
            x_pos = x_base + 50
            draw_order = ["SW-UPS", "SW-CCTV", "SW-DATA", "SW-IPTV", "SW-TEL", "SW-WIFI", "SW-CORE", "SW-FIREWALL"]
            items_a_dibujar = [item for item in draw_order if item in torre['switches']]

            y_cursor = y_sotano
            if items_a_dibujar:
                y_cursor -= 50 # Un margen superior

            coords[torre_id]['switches'] = {}

            for item_nombre in reversed(items_a_dibujar):
                if item_nombre == 'SW-UPS':
                    if torre_id == 0:
                        y_cursor -= cfg['UPS_ALTO']
                        dibujar_ups(f, cfg, x_pos, y_cursor)
                        coords['ups_coord'] = (x_pos + cfg['UPS_ANCHO'] / 2, y_cursor + cfg['UPS_ALTO'] / 2)
                        y_cursor -= cfg.get('UPS_SWITCH_GAP', 30)
                else:
                    y_cursor -= cfg['SWITCH_ALTO']
                    dibujar_switch(f, cfg, x_pos, y_cursor, item_nombre, torre['switches'][item_nombre])
                    coords[torre_id]['switches'][item_nombre] = (x_pos + cfg['SWITCH_ANCHO'] / 2, y_cursor + cfg['SWITCH_ALTO'])
                    y_cursor -= (cfg['SWITCH_VERTICAL_SPACING'] - cfg['SWITCH_ALTO'])
            lisp_escribir(f, '(princ "DONE.")')

            # Dibujar Dispositivos por nivel en orden vertical
            lisp_escribir(f, f'(princ "\\n   - Dibujando dispositivos por nivel...")')
            device_draw_order = ["apQty", "telQty", "tvQty", "datQty", "camQty"]
            for nivel_id, nivel_data in torre['niveles'].items():
                y_nivel = alturas_niveles[nivel_id]
                x_dispositivo = x_base + 150
                y_dispositivo_cursor = y_nivel + cfg['DISPOSITIVO_Y_OFFSET']

                for tipo_qty in device_draw_order:
                    conf = cfg['DISPOSITIVOS'].get(tipo_qty)
                    if not conf: continue
                    cantidad = nivel_data.get(tipo_qty, 0)
                    if cantidad > 0:
                        globals()[f"dibujar_icono_{conf['icono']}"](f, cfg, x_dispositivo, y_dispositivo_cursor)
                        lisp_dibujar_texto(f, (x_dispositivo, y_dispositivo_cursor - 20), 10, f"{cantidad}x{conf['label']}")
                        coords[torre_id][f'disp_{nivel_id}_{conf["label"]}'] = (x_dispositivo, y_dispositivo_cursor)
                        y_dispositivo_cursor += cfg.get('DISPOSITIVO_ESPACIADO_Y', 60)
            lisp_escribir(f, '(princ "DONE.")')

        # --- DIBUJAR LÍNEAS DE NIVEL ---
        lisp_escribir(f, "\n; === DIBUJAR LÍNEAS DE NIVEL ===")
        lisp_escribir(f, '(princ "\\nDibujando lineas de Nivel...")')
        for nivel_id, y_nivel in alturas_niveles.items():
            lisp_seleccionar_capa_y_color(f, "Niveles", cfg['CAPAS']['Niveles'])
            x_start_nivel = cfg['X_INICIAL'] - 50
            if 'ups_coord' in coords:
                 x_start_nivel = coords['ups_coord'][0] - cfg['UPS_ANCHO']/2 - 20

            p1 = (x_start_nivel, y_nivel)
            p2 = (torres[-1]['x'] + cfg['LONGITUD_PISO'] + 50, y_nivel)
            lisp_dibujar_linea(f, p1, p2)
            nivel_nombre = next((t['niveles'][nivel_id]['nivel_nombre'] for t in torres if nivel_id in t['niveles']), f"NIVEL {nivel_id}")
            lisp_dibujar_texto(f, (p1[0] + 10, y_nivel + 10), 15, nivel_nombre)
        lisp_escribir(f, '(princ "DONE.")')

        # --- DIBUJAR CABLES ---
        lisp_escribir(f, "\n; === DIBUJAR CABLES ===")
        dibujar_cableado_utp(f, cfg, torres, coords, alturas_niveles)
        dibujar_cableado_fibra(f, cfg, torres, coords, alturas_niveles)

        # ... (resto de la función sin cambios)
        lisp_escribir(f, '(princ "\\nDibujando alimentacion desde UPS...")')
        if 'ups_coord' in coords:
            p_origen_ups = coords['ups_coord']

            idfs = [t for t in torres if t['id'] != 0]
            todos_sw_tipos_en_idfs = sorted(list(set(sw_tipo for idf in idfs for sw_tipo in idf['switches'] if sw_tipo in cfg['SWITCH_CONFIG'])))
            num_tipos_fibra = len(todos_sw_tipos_en_idfs)
            y_bandeja_ups = coords['ups_coord'][1] - 150 - (num_tipos_fibra * 40) - 40

            lisp_seleccionar_capa_y_color(f, "UPS", cfg['CAPAS']['UPS'])

            p_drop_ups = (p_origen_ups[0], y_bandeja_ups)
            lisp_dibujar_linea(f, p_origen_ups, p_drop_ups)

            max_x_switch = 0
            for torre in torres:
                for sw in torre['switches']:
                    if sw == 'SW-UPS': continue
                    sw_coord = coords[torre['id']]['switches'][sw]
                    max_x_switch = max(max_x_switch, sw_coord[0])

            if max_x_switch > 0:
                p_end_tray_bus = (max_x_switch, y_bandeja_ups)
                lisp_dibujar_linea(f, p_drop_ups, p_end_tray_bus)

            for torre_cableado in torres:
                torre_id_cableado = torre_cableado['id']
                if torre_id_cableado in coords and 'switches' in coords[torre_id_cableado]:
                    for sw_nombre, p_destino_sw_top in coords[torre_id_cableado]['switches'].items():
                        if sw_nombre == 'SW-UPS': continue
                        p_end_sw = (p_destino_sw_top[0], p_destino_sw_top[1] - cfg['SWITCH_ALTO'] / 2)
                        p_rise_sw = (p_end_sw[0], y_bandeja_ups)
                        if p_rise_sw[0] > p_drop_ups[0]:
                            lisp_dibujar_linea(f, p_rise_sw, p_end_sw)

        lisp_escribir(f, '(princ "DONE.")')

        # --- FINALIZAR DIBUJO ---
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
        total_cable_utp = total_puntos_red * 15 # Estimación de 15m por punto

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
            f.write(f"- {sw_nombre:<15}: {cantidad} unidades\n")
            if sw_nombre in modelos_switches:
                for modelo, q in modelos_switches[sw_nombre].items():
                    f.write(f"    - Modelo: {modelo} ({q} uds)\n")
        f.write("\n")

        f.write("--- ESTIMACIÓN DE CABLEADO ---\n")
        f.write(f"- Cable UTP CAT6A: ~{total_cable_utp:,} metros\n")
        # Cálculo simple de fibra
        total_fibra = (len(torres) -1) * len(cfg['SWITCH_CONFIG']) * 50
        f.write(f"- Fibra Óptica:    ~{total_fibra:,} metros (estimación bruta)\n\n")

        f.write("--- OBSERVACIONES ---\n")
        f.write("- Las cantidades se basan en el archivo 'torres.csv'.\n")
        f.write("- La longitud del cableado es una estimación y requiere verificación en sitio.\n")
        f.write("- Se incluye 1 UPS centralizada en el MDF.\n")
        f.write("============================================================\n")
    logging.info(f"Archivo BOM '{BOM_OUTPUT_FILE}' generado con éxito.")

def main():
    """Función principal para ejecutar el script."""
    try:
        logging.info("--- INICIO DEL PROCESO DE GENERACIÓN DE PLANOS ---")
        config = cargar_configuracion()
        datos_torres = cargar_datos_csv()

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
