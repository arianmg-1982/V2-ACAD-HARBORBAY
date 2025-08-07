# Este script generará los archivos CSV necesarios para el proyecto HARBORBAY.
# Se basa en una configuración externa para generar un conjunto de datos coherente.
import csv
import random
import os
import json
from collections import defaultdict

# --- CONFIGURACION GENERAL ---
# Directorio de salida para los archivos CSV generados.
OUTPUT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(OUTPUT_DIR, "config_apartamentos.json")
NUM_TORRES = 15
NUM_NIVELES = 7

# --- MODELOS DE DISPOSITIVOS ---
# Asigna un modelo específico a cada tipo de dispositivo.
DEVICE_MODELS = {
    "telefono": "Yealink T46S",
    "AP": "Meraki MR46",
    "TV": "Apple TV 4K"
}

# --- CONFIGURACION DE SWITCHES ---
# Define la configuración de switches que se replicará en cada torre IDF.
SWITCH_CONFIG = {
    "torre_nombre": "", # Se llenará dinámicamente
    "nivel_nombre": "SOTANO",
    "switch_wifi": 1,
    "switch_tel": 1,
    "switch_iptv": 1,
    "switch_cctv": 1,
    "switch_data": 1,
    "modelo_wifi": "Meraki MS225",
    "modelo_tel": "Meraki MS225",
    "modelo_iptv": "RG-NBS6002",
    "modelo_cctv": "DS-3E3728F",
    "modelo_data": "Meraki MS225"
}

def load_apartment_config():
    """
    Carga la configuración de apartamentos desde el archivo JSON.
    """
    print(f"Cargando configuración desde {CONFIG_FILE}...")
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: El archivo de configuración '{CONFIG_FILE}' no fue encontrado.")
        raise
    except json.JSONDecodeError:
        print(f"Error: El archivo '{CONFIG_FILE}' no es un JSON válido.")
        raise

def generar_tipos_apartamento_csv(apartment_types):
    """
    Genera el archivo tipos_apartamento.csv con la definición de cada tipo.
    """
    filepath = os.path.join(OUTPUT_DIR, "tipos_apartamento.csv")
    print(f"Generando {filepath}...")
    headers = ["tipo", "habitaciones", "telefono", "ap", "tv"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for tipo, data in apartment_types.items():
            row = [
                tipo,
                data["habitaciones"],
                data["dispositivos"]["telefono"],
                data["dispositivos"]["AP"],
                data["dispositivos"]["TV"],
            ]
            writer.writerow(row)

def generar_dispositivos_por_apartamento_csv(apartment_types):
    """
    Genera el archivo dispositivos_por_apartamento.csv con los modelos y cantidades.
    """
    filepath = os.path.join(OUTPUT_DIR, "dispositivos_por_apartamento.csv")
    print(f"Generando {filepath}...")
    headers = ["tipo_apartamento", "dispositivo", "cantidad", "modelo"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for apt_type, data in apartment_types.items():
            for device_type, count in data["dispositivos"].items():
                row = [
                    apt_type,
                    device_type,
                    count,
                    DEVICE_MODELS.get(device_type, "N/A")
                ]
                writer.writerow(row)

def generar_switches_csv():
    """
    Genera el archivo switches.csv para cada una de las 15 torres.
    """
    filepath = os.path.join(OUTPUT_DIR, "switches.csv")
    print(f"Generando {filepath}...")
    headers = list(SWITCH_CONFIG.keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for i in range(1, NUM_TORRES + 1):
            row = SWITCH_CONFIG.copy()
            row["torre_nombre"] = f"IDF{i}"
            writer.writerow(row)

def generar_distribucion_apartamentos(apartment_types):
    """
    Genera una distribución aleatoria de los apartamentos en las torres y niveles.
    """
    filepath = os.path.join(OUTPUT_DIR, "apartamentos.csv")
    print(f"Generando {filepath}...")

    lista_apartamentos = []
    for apt_type, data in apartment_types.items():
        for _ in range(data["count"]):
            lista_apartamentos.append(apt_type)

    random.shuffle(lista_apartamentos)

    ubicaciones = []
    for id_torre in range(1, NUM_TORRES + 1):
        for id_nivel in range(1, NUM_NIVELES + 1):
            ubicaciones.append({
                "torre_nombre": f"IDF{id_torre}",
                "nivel_nombre": f"NIVEL{id_nivel}"
            })

    apartamentos_distribuidos = []
    headers = ["id_apartamento", "torre_nombre", "nivel_nombre", "tipo_apartamento", "habitaciones"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for i, apt_type in enumerate(lista_apartamentos):
            id_apartamento = i + 1
            ubicacion = random.choice(ubicaciones)

            apartamento_data = {
                "id_apartamento": id_apartamento,
                "torre_nombre": ubicacion["torre_nombre"],
                "nivel_nombre": ubicacion["nivel_nombre"],
                "tipo_apartamento": apt_type,
                "habitaciones": apartment_types[apt_type]["habitaciones"]
            }
            apartamentos_distribuidos.append(apartamento_data)
            writer.writerow(apartamento_data.values())

    return apartamentos_distribuidos

def generar_dispositivos_csv(apartamentos_distribuidos, apartment_types):
    """
    Genera el archivo dispositivos.csv con la lista detallada de cada dispositivo.
    """
    filepath = os.path.join(OUTPUT_DIR, "dispositivos.csv")
    print(f"Generando {filepath}...")
    headers = ["id_dispositivo", "tipo", "modelo", "id_apartamento", "torre_nombre", "nivel_nombre", "ubicacion"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for apt in apartamentos_distribuidos:
            apt_type = apt["tipo_apartamento"]
            apt_id = apt["id_apartamento"]
            config_dispositivos = apartment_types[apt_type]["dispositivos"]

            for i in range(config_dispositivos["telefono"]):
                writer.writerow([f"TEL-{apt_id}-{i+1}", "telefono", DEVICE_MODELS["telefono"], apt_id, apt["torre_nombre"], apt["nivel_nombre"], f"Apartamento {apt_id} - Teléfono {i+1}"])
            for i in range(config_dispositivos["AP"]):
                writer.writerow([f"AP-{apt_id}-{i+1}", "AP", DEVICE_MODELS["AP"], apt_id, apt["torre_nombre"], apt["nivel_nombre"], f"Apartamento {apt_id} - AP {i+1}"])
            for i in range(config_dispositivos["TV"]):
                writer.writerow([f"TV-{apt_id}-{i+1}", "TV", DEVICE_MODELS["TV"], apt_id, apt["torre_nombre"], apt["nivel_nombre"], f"Apartamento {apt_id} - TV {i+1}"])

def generar_distribucion_por_nivel_csv(apartamentos_distribuidos):
    """
    Genera el archivo distribucion_apartamentos_por_nivel.csv.
    """
    filepath = os.path.join(OUTPUT_DIR, "distribucion_apartamentos_por_nivel.csv")
    print(f"Generando {filepath}...")
    headers = ["nivel_nombre", "tipo_apartamento", "cantidad"]

    counts = defaultdict(lambda: defaultdict(int))
    for apt in apartamentos_distribuidos:
        counts[apt["nivel_nombre"]][apt["tipo_apartamento"]] += 1

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for nivel, tipos in sorted(counts.items()):
            for tipo, cantidad in sorted(tipos.items()):
                writer.writerow([nivel, tipo, cantidad])

def generar_resumen_global_csv(apartamentos_distribuidos, apartment_types):
    """
    Genera el archivo resumen_global.csv con los totales del proyecto.
    """
    filepath = os.path.join(OUTPUT_DIR, "resumen_global.csv")
    print(f"Generando {filepath}...")
    headers = ["dispositivo", "total"]

    totals = defaultdict(int)
    total_apartments = len(apartamentos_distribuidos)

    for apt in apartamentos_distribuidos:
        apt_type_config = apartment_types[apt["tipo_apartamento"]]
        for device, count in apt_type_config["dispositivos"].items():
            totals[device] += count

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for device, total in sorted(totals.items()):
            writer.writerow([device, total])
        writer.writerow(["Departamentos", total_apartments])

def generar_torres_csv(apartamentos_distribuidos, apartment_types):
    """
    Genera el archivo final torres.csv, que es el input para el script principal.
    """
    filepath = os.path.join(OUTPUT_DIR, "torres.csv")
    print(f"Generando archivo final {filepath}...")

    datos_agregados = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for apt in apartamentos_distribuidos:
        torre_id = int(apt["torre_nombre"].replace("IDF", ""))
        nivel_id = int(apt["nivel_nombre"].replace("NIVEL", ""))

        apt_config = apartment_types[apt["tipo_apartamento"]]["dispositivos"]
        datos_agregados[torre_id][nivel_id]["apQty"] += apt_config["AP"]
        datos_agregados[torre_id][nivel_id]["telQty"] += apt_config["telefono"]
        datos_agregados[torre_id][nivel_id]["tvQty"] += apt_config["TV"]

    headers = ["TORRE", "torre_nombre", "NIVEL", "nivel_nombre", "apQty", "telQty", "tvQty", "camQty", "datQty", "ap_modelo", "tel_modelo", "tv_modelo", "cam_modelo", "dat_modelo", "switch_UPS", "switch_FIREWALL", "switch_CORE", "switch_wifi", "switch_tel", "switch_iptv", "switch_cctv", "switch_data", "switch_UPS_modelo", "switch_FIREWALL_modelo", "switch_CORE_modelo", "switch_wifi_modelo", "switch_tel_modelo", "switch_iptv_modelo", "switch_cctv_modelo", "switch_data_modelo"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        writer.writerow({"TORRE": 0, "torre_nombre": "MDF", "NIVEL": 0, "nivel_nombre": "SOTANO", "apQty": 0, "telQty": 0, "tvQty": 0, "camQty": 0, "datQty": 0, "switch_UPS": 1, "switch_FIREWALL": 0, "switch_CORE": 0, "switch_wifi": 1, "switch_tel": 1, "switch_iptv": 1, "switch_cctv": 1, "switch_data": 1, "switch_UPS_modelo": "UPS", "switch_wifi_modelo": SWITCH_CONFIG["modelo_wifi"], "switch_tel_modelo": SWITCH_CONFIG["modelo_tel"], "switch_iptv_modelo": SWITCH_CONFIG["modelo_iptv"], "switch_cctv_modelo": SWITCH_CONFIG["modelo_cctv"], "switch_data_modelo": SWITCH_CONFIG["modelo_data"]})

        for torre_id in range(1, NUM_TORRES + 1):
            sotano_row = {"TORRE": torre_id, "torre_nombre": f"IDF{torre_id}", "NIVEL": 0, "nivel_nombre": "SOTANO", "apQty": 0, "telQty": 0, "tvQty": 0, "camQty": 0, "datQty": 0, "switch_wifi": 1, "switch_tel": 1, "switch_iptv": 1, "switch_cctv": 1, "switch_data": 1, "switch_wifi_modelo": SWITCH_CONFIG["modelo_wifi"], "switch_tel_modelo": SWITCH_CONFIG["modelo_tel"], "switch_iptv_modelo": SWITCH_CONFIG["modelo_iptv"], "switch_cctv_modelo": SWITCH_CONFIG["modelo_cctv"], "switch_data_modelo": SWITCH_CONFIG["modelo_data"]}
            writer.writerow(sotano_row)
            for nivel_id in range(1, NUM_NIVELES + 1):
                cantidades = datos_agregados[torre_id][nivel_id]
                writer.writerow({"TORRE": torre_id, "torre_nombre": f"IDF{torre_id}", "NIVEL": nivel_id, "nivel_nombre": f"NIVEL{nivel_id}", "apQty": cantidades["apQty"], "telQty": cantidades["telQty"], "tvQty": cantidades["tvQty"], "camQty": 0, "datQty": 0})

def main():
    """
    Función principal para orquestar la generación de todos los archivos CSV.
    """
    try:
        print("Iniciando la generación de archivos CSV auxiliares para Harbor Bay...")

        apartment_types = load_apartment_config()

        generar_tipos_apartamento_csv(apartment_types)
        generar_dispositivos_por_apartamento_csv(apartment_types)
        generar_switches_csv()
        print("\nArchivos de definición generados.")

        apartamentos_data = generar_distribucion_apartamentos(apartment_types)
        generar_dispositivos_csv(apartamentos_data, apartment_types)
        print("Distribución de apartamentos y dispositivos generada.")

        generar_distribucion_por_nivel_csv(apartamentos_data)
        generar_resumen_global_csv(apartamentos_data, apartment_types)
        print("Archivos de resumen generados.")

        generar_torres_csv(apartamentos_data, apartment_types)
        print("Archivo final torres.csv generado.")

        print("\n--- Proceso de generación completado exitosamente ---")
    except Exception as e:
        print(f"\nHa ocurrido un error: {e}")

if __name__ == "__main__":
    main()
