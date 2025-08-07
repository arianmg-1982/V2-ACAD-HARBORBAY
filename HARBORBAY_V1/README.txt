Este archivo explica el propósito de los archivos de configuración utilizados por los scripts de generación.

================================================
1. config_apartamentos.json
================================================
Este archivo define la estructura y cantidad de los apartamentos en el proyecto. Es el archivo principal que se debe modificar para cambiar la distribución de apartamentos.

Ejemplo de un tipo de apartamento:
"1H": {
    "count": 4,
    "habitaciones": 1,
    "dispositivos": {"telefono": 1, "AP": 2, "TV": 2}
}

- "1H": Es el identificador del tipo de apartamento (ej. 1 Habitación). Puede ser cualquier texto.
- "count": Es el número total de apartamentos de este tipo que existirán en todo el proyecto.
- "habitaciones": Es el número de habitaciones (meramente informativo).
- "dispositivos": Es un diccionario que define cuántos dispositivos de cada tipo tiene este apartamento.
    - "telefono": Cantidad de teléfonos.
    - "AP": Cantidad de Puntos de Acceso (Access Points).
    - "TV": Cantidad de televisores.

El script `generador_auxiliar_de_csv.py` lee este archivo para crear todos los demás archivos CSV.

================================================
2. config.json
================================================
Este archivo controla los parámetros de DIBUJO del script que genera el archivo de AutoLISP (`generar_lisp_HARBORBAY.py`). Modificar estos valores cambiará la apariencia del plano generado.

Parámetros Principales:
----------------------
- "X_INICIAL", "Y_INICIAL": Coordenadas (X, Y) donde empieza a dibujarse la primera torre (MDF).
- "ESPACIO_ENTRE_NIVELES": Distancia vertical entre las líneas que representan cada nivel.
- "LONGITUD_PISO": Ancho visual de la línea que representa un piso de una torre.
- "SEPARACION_ENTRE_TORRES": Distancia horizontal entre una torre y la siguiente.

Parámetros de Componentes:
--------------------------
- "SWITCH_ANCHO", "SWITCH_ALTO": Dimensiones de los rectángulos que representan los switches.
- "UPS_ANCHO", "UPS_ALTO": Dimensiones del rectángulo que representa la UPS.
- "DISPOSITIVO_ESPACIADO_X", "DISPOSITIVO_ESPACIADO_Y": Espaciado entre los iconos de los dispositivos en el dibujo.

Mapeos y Configuraciones:
---------------------------
- "CAPAS": Asocia un nombre de capa de AutoCAD con un número de color.
- "MAPEO_SWITCH": Asocia un tipo de dispositivo (ej. "apQty") con el tipo de switch al que debe conectarse (ej. "SW-WIFI").
- "DISPOSITIVOS": Define propiedades para cada tipo de dispositivo, como la etiqueta que se usará en el dibujo ("label") y el nombre del icono a dibujar ("icono").
- "SWITCH_DRAW_ORDER": Define el orden vertical en que se dibujan los switches dentro de una torre.
