"""Minilenguaje de monitoreo simulado: análisis, semántica y traducción a pila."""
from functools import lru_cache
import re
from automatas import EXPRESIONES
from slr import generar_slr, analizar_sintaxis

EJEMPLO = "CARGAR S01 = 28;\nCARGAR S02 = 15;\nSI S01 > 26 Y S02 < 20 ENTONCES AVISAR A01;"
LITERALES = {s: s for s in ["CARGAR", "SI", "Y", "ENTONCES", "AVISAR"]}
LITERALES[";"] = "PUNTO_Y_COMA"
PATRONES_TOKENS = {**EXPRESIONES, **{nombre: re.escape(lexema) for lexema, nombre in LITERALES.items()}}
SENSORES = {"S01": {"descripcion": "Temperatura simulada del equipo", "minimo": 0, "maximo": 50},
            "S02": {"descripcion": "Batería simulada del equipo (%)", "minimo": 0, "maximo": 100}}
ACCIONES = {"A01": "Revisión técnica simulada", "A02": "Mantenimiento preventivo simulado"}
LIMITES = {"caracteres": 65536, "tokens": 300, "instrucciones": 50, "codigo": 1000}
DESCRIPCIONES = {"SENSOR": "Código de sensor; su existencia se comprueba semánticamente.",
    "ACCION": "Código de aviso simulado.", "NUMERO": "Entero decimal no negativo.",
    "COMPARADOR": "Comparación de enteros.", "IGUAL": "Asignación de un valor."}
GRAMATICA = {"inicial": "P", "producciones": [
    ["P", ["CARGAS", "REGLAS"]], ["CARGAS", ["CARGA", "CARGAS"]], ["CARGAS", ["CARGA"]],
    ["REGLAS", ["REGLA", "REGLAS"]], ["REGLAS", ["REGLA"]],
    ["CARGA", ["CARGAR", "SENSOR", "IGUAL", "NUMERO", "PUNTO_Y_COMA"]],
    ["REGLA", ["SI", "COND", "ENTONCES", "AVISAR", "ACCION", "PUNTO_Y_COMA"]],
    ["COND", ["COMP", "RESTO"]], ["RESTO", ["Y", "COMP", "RESTO"]], ["RESTO", []],
    ["COMP", ["SENSOR", "COMPARADOR", "NUMERO"]]]}
OPERADORES = {">": "GT", "<": "LT", ">=": "GE", "<=": "LE", "==": "EQ", "!=": "NE"}


@lru_cache(maxsize=1)
def tabla_slr():
    return generar_slr(GRAMATICA)


def analizar(texto):
    tokens, errores = [], []
    for numero, linea in enumerate(texto.splitlines(), 1):
        pos = 0
        while pos < len(linea):
            if linea[pos].isspace():
                pos += 1
                continue
            inicio = pos
            if linea[pos] == ";":
                pos += 1
            elif linea[pos] in "=<>!":
                pos += 2 if linea[pos:pos + 2] in ("<=", ">=", "==", "!=") else 1
            else:
                while pos < len(linea) and not linea[pos].isspace() and linea[pos] not in ";=<>!":
                    pos += 1
            lexema = linea[inicio:pos]
            nombre = next((n for n, patron in PATRONES_TOKENS.items() if re.fullmatch(patron, lexema)), None)
            elemento = {"linea": numero, "columna": inicio + 1, "lexema": lexema}
            if nombre:
                tokens.append({**elemento, "token": nombre})
            else:
                errores.append({**elemento, "detalle": "Lexema no reconocido; respeta códigos completos, operadores y mayúsculas."})
    return tokens, errores


def reducir(izquierda, a):
    """Atributos sintetizados construidos durante las reducciones SLR reales."""
    if izquierda == "P":
        return {"cargas": a[0], "reglas": a[1]}
    if izquierda in ("CARGAS", "REGLAS"):
        return [a[0]] + (a[1] if len(a) == 2 else [])
    if izquierda == "CARGA":
        return {"sensor": a[1]["lexema"], "valor": a[3]["lexema"], "linea": a[1]["linea"],
                "columna": a[1]["columna"], "columna_valor": a[3]["columna"]}
    if izquierda == "REGLA":
        return {"comparaciones": a[1], "accion": a[4]["lexema"], "linea": a[4]["linea"], "columna": a[4]["columna"]}
    if izquierda == "COND":
        return [a[0]] + a[1]
    if izquierda == "RESTO":
        return [a[1]] + a[2] if a else []
    return {"sensor": a[0]["lexema"], "comparador": a[1]["lexema"], "valor": a[2]["lexema"],
            "linea": a[0]["linea"], "columna": a[0]["columna"], "columna_valor": a[2]["columna"]}


def validar_semantica(programa):
    atributos, errores, cargados = [], [], set()

    def comprobar(campo, lexema, tipo, accion, valido, elemento, columna=None):
        atributos.append({"campo": campo, "lexema": lexema, "tipo": tipo, "accion": accion,
                          "valido": valido, "linea": elemento["linea"]})
        if not valido:
            errores.append({"linea": elemento["linea"], "columna": columna or elemento["columna"], "lexema": lexema, "detalle": accion + ": " + lexema})

    def sensor_valor(e, carga):
        sensor = e["sensor"]
        conocido = sensor in SENSORES
        comprobar("sensor", sensor, "sensor", "Código de sensor conocido", conocido, e)
        comprobar("referencia", sensor, "referencia", "Carga única" if carga else "Sensor cargado previamente",
                  sensor not in cargados if carga else sensor in cargados, e)
        normal = e["valor"].lstrip("0") or "0"
        valor = int(normal) if len(normal) <= 3 else 1000
        valido = conocido and SENSORES[sensor]["minimo"] <= valor <= SENSORES[sensor]["maximo"]
        comprobar("valor", e["valor"], "entero", "Valor dentro del rango del sensor", valido, e, e["columna_valor"])
        if carga:
            cargados.add(sensor)

    for carga in programa["cargas"]:
        sensor_valor(carga, True)
    for regla in programa["reglas"]:
        for comparacion in regla["comparaciones"]:
            sensor_valor(comparacion, False)
            comprobar("comparador", comparacion["comparador"], "operador", "Comparador permitido",
                      comparacion["comparador"] in OPERADORES, comparacion)
        comprobar("accion", regla["accion"], "accion", "Código de acción conocido", regla["accion"] in ACCIONES, regla)
    return atributos, errores


def traducir(programa):
    codigo, correspondencias = [], []
    for carga in programa["cargas"]:
        codigo.extend([{"op": "PUSH", "arg": int(carga["valor"].lstrip("0") or "0")}, {"op": "STORE", "arg": carga["sensor"]}])
    for i, regla in enumerate(programa["reglas"], 1):
        inicio, etiqueta = len(codigo), "L" + str(i)
        for c in regla["comparaciones"]:
            codigo.extend([{"op": "LOAD", "arg": c["sensor"]}, {"op": "PUSH", "arg": int(c["valor"].lstrip("0") or "0")},
                           {"op": OPERADORES[c["comparador"]]}, {"op": "JUMP_IF_FALSE", "arg": etiqueta}])
        codigo.extend([{"op": "EMIT", "arg": regla["accion"]}, {"op": "LABEL", "arg": etiqueta}])
        correspondencias.append({"regla": i, "linea": regla["linea"], "inicio": inicio, "fin": len(codigo) - 1, "etiqueta": etiqueta})
    return codigo, correspondencias


def compilar(texto):
    from simulador import ejecutar
    slr = tabla_slr()
    tokens, errores = ([], [{"linea": 1, "columna": 1, "lexema": "", "detalle": "Límite de entrada: 65536 caracteres."}]) if len(texto) > LIMITES["caracteres"] else analizar(texto)
    if len(tokens) > LIMITES["tokens"]:
        errores.append({"linea": 1, "columna": 1, "lexema": "", "detalle": "Límite de 300 tokens excedido."})
        tokens = tokens[:LIMITES["tokens"]]
    r = {"aceptado": False, "arbol": None, "derivacion": [], "traza": [], "estructura": None, "errores_sintacticos": []}
    if not errores:
        r = analizar_sintaxis(tokens, slr, reducir)
    r.update(linea=1, sintaxis_aceptada=r["aceptado"], fase="léxico" if errores else "sintáctico",
             atributos=[], errores_semanticos=[], salida=None)
    codigo, correspondencias, simulacion = [], [], None
    if r["aceptado"]:
        r["atributos"], r["errores_semanticos"] = validar_semantica(r["estructura"])
        if len(r["estructura"]["cargas"]) + len(r["estructura"]["reglas"]) > LIMITES["instrucciones"]:
            r["errores_semanticos"].append({"linea": 1, "columna": 1, "detalle": "Límite de 50 instrucciones excedido."})
        r["aceptado"] = not r["errores_semanticos"]
        r["fase"] = "aceptado" if r["aceptado"] else "semántico"
        if r["aceptado"]:
            codigo, correspondencias = traducir(r["estructura"])
            simulacion = ejecutar(codigo)
            r["salida"] = {"estado": "aceptado", "avisos": simulacion["avisos"]}
    return {"tokens": tokens, "errores": errores, "registros": [r], "aceptado": r["aceptado"], "slr": slr,
            "salida": r["salida"], "codigo": codigo, "correspondencias": correspondencias, "simulacion": simulacion}
