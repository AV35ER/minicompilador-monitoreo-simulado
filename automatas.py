
from functools import lru_cache
from collections import deque
from graphviz import Digraph, nohtml
from xml.etree.ElementTree import Element, SubElement, tostring

EXPRESIONES = {
    "SENSOR": "S[0-9][0-9]", "ACCION": "A[0-9][0-9]", "NUMERO": "[0-9]+",
    "COMPARADOR": "<=|>=|==|!=|<|>", "IGUAL": "="
}
CONSTRUCCIONES_DIRECTAS = {
    "SENSOR": (4, [3], [(0, "S", 1), (1, "[0-9]", 2), (2, "[0-9]", 3)]),
    "ACCION": (4, [3], [(0, "A", 1), (1, "[0-9]", 2), (2, "[0-9]", 3)]),
    "NUMERO": (2, [1], [(0, "[0-9]", 1), (1, "[0-9]", 1)]),
    "COMPARADOR": (4, [1, 3], [(0, "<", 1), (0, ">", 1), (0, "=", 2), (0, "!", 2), (1, "=", 3), (2, "=", 3)]),
    "IGUAL": (2, [1], [(0, "=", 1)])
}


def crear_directo(token):
    cantidad, finales, aristas = CONSTRUCCIONES_DIRECTAS[token]
    return {"estados": [f"q{i}" for i in range(cantidad)], "inicial": "q0",
            "finales": [f"q{i}" for i in finales], "transiciones": [
                {"origen": f"q{a}", "simbolo": c, "destino": f"q{b}"}
                for a, s, b in aristas for c in expandir_simbolo(s)]}


def sin_sumidero(automata, muertos):
    """Representación parcial: transición ausente = rechazo, sin alterar el lenguaje."""
    return {**automata,
            "estados": [e for e in automata["estados"] if e not in muertos],
            "finales": [e for e in automata["finales"] if e not in muertos],
            "transiciones": [t for t in automata["transiciones"]
                             if t["origen"] not in muertos and t["destino"] not in muertos],
            "equivalencias": {e: g for e, g in automata["equivalencias"].items() if e not in muertos}}


EJEMPLOS = {
    "SENSOR": (["S01", "S02", "S99"], ["s01", "S011", "S1"]),
    "ACCION": (["A01", "A02", "A99"], ["a01", "A001", "A1"]),
    "NUMERO": (["0", "28", "100"], ["-1", "2.5", "1x"]),
    "COMPARADOR": (["<", ">", "<=", ">=", "==", "!="], ["!", "=", "==="]),
    "IGUAL": (["="], ["==", "!=", ":="])
}


def expandir_simbolo(simbolo):
    if simbolo == "ε":
        return []
    if simbolo.startswith("[") and simbolo.endswith("]"):
        contenido = simbolo[1:-1]
        caracteres = []
        i = 0
        while i < len(contenido):
            if i + 2 < len(contenido) and contenido[i + 1] == "-":
                inicio, fin = ord(contenido[i]), ord(contenido[i + 2])
                if inicio > fin:
                    raise ValueError("Rango invertido")
                caracteres.extend(chr(n) for n in range(inicio, fin + 1))
                i += 3
            else:
                caracteres.append(contenido[i])
                i += 1
        return sorted(set(caracteres))
    return [simbolo]


class ParserRegex:
    """Descenso recursivo: alternativa > concatenación > repetición > átomo.

    Produce un árbol de tuplas. No usa re ni plantillas de estados por token.
    Admite clases positivas, grupos, |, *, +, ?, {n}, {m,n} y {m,}.
    """
    def __init__(self, expresion):
        self.texto = expresion
        self.pos = 0

    def ver(self):
        return self.texto[self.pos:self.pos + 1]

    def analizar(self):
        nodo = self.alternativa()
        if self.pos != len(self.texto):
            raise ValueError("Símbolo inesperado en posición " + str(self.pos))
        return nodo

    def alternativa(self):
        nodos = [self.concatenacion()]
        while self.ver() == "|":
            self.pos += 1
            nodos.append(self.concatenacion())
        return ("alternativa", nodos) if len(nodos) > 1 else nodos[0]

    def concatenacion(self):
        nodos = []
        while self.ver() and self.ver() not in "|)":
            nodos.append(self.repeticion())
        return ("concatenacion", nodos)

    def repeticion(self):
        nodo = self.atomo()
        signo = self.ver()
        if signo and signo in "*+?":
            self.pos += 1
            limites = {"*": (0, None), "+": (1, None), "?": (0, 1)}
            return ("repeticion", nodo, *limites[signo])
        if signo == "{":
            fin = self.texto.find("}", self.pos)
            if fin == -1:
                raise ValueError("Repetición sin cierre")
            partes = self.texto[self.pos + 1:fin].split(",")
            if len(partes) > 2 or not partes[0].isascii() or not partes[0].isdigit():
                raise ValueError("Repetición inválida")
            minimo = int(partes[0])
            maximo = minimo
            if len(partes) == 2:
                if partes[1] and (not partes[1].isascii() or not partes[1].isdigit()):
                    raise ValueError("Repetición inválida")
                maximo = int(partes[1]) if partes[1] else None
            if maximo is not None and maximo < minimo:
                raise ValueError("Límites invertidos")
            self.pos = fin + 1
            return ("repeticion", nodo, minimo, maximo)
        return nodo

    def atomo(self):
        signo = self.ver()
        self.pos += 1
        if signo == "(":
            nodo = self.alternativa()
            if self.ver() != ")":
                raise ValueError("Grupo sin cierre")
            self.pos += 1
            return nodo
        if signo == "[":
            fin = self.texto.find("]", self.pos)
            if fin == -1:
                raise ValueError("Clase sin cierre")
            valor = self.texto[self.pos - 1:fin + 1]
            if valor.startswith("[^") or "\\" in valor or not expandir_simbolo(valor):
                raise ValueError("Se requieren clases positivas no vacías")
            self.pos = fin + 1
            return ("simbolo", valor)
        if signo == "\\":
            signo = self.ver()
            if not signo:
                raise ValueError("Escape incompleto")
            self.pos += 1
            if signo.isalnum():
                raise ValueError("Solo se admiten escapes de signos literales")
        elif signo in "*+?{}].^" or signo == "ε":
            raise ValueError("Operador no soportado o sin operando")
        return ("simbolo", signo)


class GeneradorAFND:
    def __init__(self):
        self.estados = []
        self.transiciones = []

    def nuevo_estado(self):
        estado = "q" + str(len(self.estados))
        self.estados.append(estado)
        return estado

    def conectar(self, origen, simbolo, destino):
        self.transiciones.append({
            "origen": origen,
            "simbolo": simbolo,
            "destino": destino
        })

    def simbolo(self, valor):
        inicio = self.nuevo_estado()
        fin = self.nuevo_estado()
        self.conectar(inicio, valor, fin)
        return inicio, fin

    def concatenar(self, a, b):
        self.conectar(a[1], "ε", b[0])
        return a[0], b[1]

    def estrella(self, fragmento):
        inicio = self.nuevo_estado()
        fin = self.nuevo_estado()

        self.conectar(inicio, "ε", fragmento[0])
        self.conectar(inicio, "ε", fin)
        self.conectar(fragmento[1], "ε", fragmento[0])
        self.conectar(fragmento[1], "ε", fin)

        return inicio, fin

    def unir(self, fragmentos):
        if not fragmentos:
            return self.simbolo("ε")
        resultado = fragmentos[0]
        for fragmento in fragmentos[1:]:
            resultado = self.concatenar(resultado, fragmento)
        return resultado

    def desde_arbol(self, nodo):
        tipo = nodo[0]
        if tipo == "simbolo":
            return self.simbolo(nodo[1])
        if tipo == "concatenacion":
            return self.unir([self.desde_arbol(hijo) for hijo in nodo[1]])
        if tipo == "alternativa":
            inicio, fin = self.nuevo_estado(), self.nuevo_estado()
            for hijo in nodo[1]:
                a, b = self.desde_arbol(hijo)
                self.conectar(inicio, "ε", a)
                self.conectar(b, "ε", fin)
            return inicio, fin
        _, hijo, minimo, maximo = nodo
        if minimo == 1 and maximo is None:
            # r+ necesita una copia de r y un bucle, no dos copias como r·r*.
            a, b = self.desde_arbol(hijo)
            inicio, fin = self.nuevo_estado(), self.nuevo_estado()
            self.conectar(inicio, "ε", a)
            self.conectar(b, "ε", a)
            self.conectar(b, "ε", fin)
            return inicio, fin
        partes = [self.desde_arbol(hijo) for _ in range(minimo)]
        if maximo is None:
            partes.append(self.estrella(self.desde_arbol(hijo)))
        else:
            for _ in range(maximo - minimo):
                a, b = self.desde_arbol(hijo)
                inicio, fin = self.nuevo_estado(), self.nuevo_estado()
                self.conectar(inicio, "ε", a)
                self.conectar(inicio, "ε", fin)
                self.conectar(b, "ε", fin)
                partes.append((inicio, fin))
        return self.unir(partes)

    def construir(self, expresion):
        arbol = ParserRegex(expresion).analizar()
        inicio, fin = self.desde_arbol(arbol)
        return {
            "estados": self.estados,
            "inicial": inicio,
            "finales": [fin],
            "transiciones": self.transiciones
        }


def crear_afnd(expresion):
    automata = GeneradorAFND().construir(expresion)
    automata["transiciones"] = [{**t, "simbolo": c} for t in automata["transiciones"]
                               for c in (["ε"] if t["simbolo"] == "ε" else expandir_simbolo(t["simbolo"]))]
    return automata


def obtener_alfabeto(automata):
    simbolos = set()

    for t in automata["transiciones"]:
        simbolos.update(expandir_simbolo(t["simbolo"]))

    return sorted(simbolos)


def cierre_epsilon(estados, transiciones):
    cierre = set(estados)
    pendientes = list(estados)

    while pendientes:
        actual = pendientes.pop()

        for t in transiciones:
            if t["origen"] == actual and t["simbolo"] == "ε":
                destino = t["destino"]

                if destino not in cierre:
                    cierre.add(destino)
                    pendientes.append(destino)

    return frozenset(cierre)


def mover(estados, simbolo, transiciones):
    destinos = set()

    for t in transiciones:
        if t["origen"] in estados and simbolo in expandir_simbolo(t["simbolo"]):
            destinos.add(t["destino"])

    return destinos


def convertir_afd(afnd):
    transiciones = afnd["transiciones"]
    alfabeto = obtener_alfabeto(afnd)

    inicial = cierre_epsilon(
        [afnd["inicial"]],
        transiciones
    )

    conjuntos = {inicial: "D0"}
    pendientes = deque([inicial])

    estados = ["D0"]
    finales = []
    nuevas_transiciones = []
    equivalencias = {}

    while pendientes:
        conjunto = pendientes.popleft()
        nombre = conjuntos[conjunto]

        equivalencias[nombre] = sorted(
            conjunto,
            key=lambda x: int(x[1:])
        )

        if any(e in afnd["finales"] for e in conjunto):
            finales.append(nombre)

        for simbolo in alfabeto:
            destinos = mover(
                conjunto,
                simbolo,
                transiciones
            )

            cierre = cierre_epsilon(
                destinos,
                transiciones
            )

            if cierre not in conjuntos:
                nuevo = "D" + str(len(conjuntos))
                conjuntos[cierre] = nuevo
                estados.append(nuevo)
                pendientes.append(cierre)

            nuevas_transiciones.append({
                "origen": nombre,
                "simbolo": simbolo,
                "destino": conjuntos[cierre]
            })

    return {
        "estados": estados,
        "inicial": "D0",
        "finales": finales,
        "transiciones": nuevas_transiciones,
        "equivalencias": equivalencias
    }


def generar_quintupla(automata):
    return {
        "Q": automata["estados"],
        "Sigma": obtener_alfabeto(automata),
        "delta": automata["transiciones"],
        "q0": automata["inicial"],
        "F": automata["finales"]
    }


def minimizar_afd(afd):
    """Refina la partición finales/no finales hasta distinguir sus futuros.

    Cada bloque estable representa una clase de estados con el mismo lenguaje
    residual. No se fusionan estados por su aspecto ni se eliminan sumideros.
    La entrada es el AFD total y alcanzable producido por convertir_afd.
    """
    alfabeto = obtener_alfabeto(afd)
    delta = {(t["origen"], t["simbolo"]): t["destino"] for t in afd["transiciones"]}
    finales = set(afd["finales"])
    bloques = [grupo for grupo in (
        [e for e in afd["estados"] if e not in finales],
        [e for e in afd["estados"] if e in finales]
    ) if grupo]
    while True:
        pertenencia = {e: i for i, grupo in enumerate(bloques) for e in grupo}
        nuevos = []
        for grupo in bloques:
            firmas = {}
            for estado in grupo:
                firma = tuple(pertenencia[delta[estado, simbolo]] for simbolo in alfabeto)
                firmas.setdefault(firma, []).append(estado)
            nuevos.extend(firmas.values())
        if len(nuevos) == len(bloques):
            break
        bloques = nuevos
    # Numeración estable, comenzando por el bloque del estado inicial.
    bloques.sort(key=lambda grupo: min(afd["estados"].index(e) for e in grupo))
    nombres = {e: "M" + str(i) for i, grupo in enumerate(bloques) for e in grupo}
    return {
        "estados": ["M" + str(i) for i in range(len(bloques))],
        "inicial": nombres[afd["inicial"]],
        "finales": ["M" + str(i) for i, grupo in enumerate(bloques) if grupo[0] in finales],
        "transiciones": [
            {"origen": "M" + str(i), "simbolo": simbolo,
             "destino": nombres[delta[grupo[0], simbolo]]}
            for i, grupo in enumerate(bloques) for simbolo in alfabeto
        ],
        "equivalencias": {"M" + str(i): grupo for i, grupo in enumerate(bloques)}
    }


def generar_tabla(automata):
    alfabeto = obtener_alfabeto(automata)
    if any(t["simbolo"] == "ε" for t in automata["transiciones"]):
        alfabeto.append("ε")
    tabla = []

    for estado in automata["estados"]:
        fila = {"estado": estado}

        for simbolo in alfabeto:
            destinos = set()

            for t in automata["transiciones"]:
                if t["origen"] == estado:
                    if simbolo == t["simbolo"] or simbolo in expandir_simbolo(t["simbolo"]):
                        destinos.add(t["destino"])

            fila[simbolo] = sorted(destinos)

        tabla.append(fila)

    return tabla


def dibujar_automata(automata, titulo="", formato="svg"):
    grafo = Digraph(format=formato)

    grafo.attr(
        rankdir="LR",
        label=titulo,
        labelloc="t",
        fontsize="18"
    )

    grafo.node("inicio", shape="point")

    for estado in automata["estados"]:
        forma = "doublecircle" if estado in automata["finales"] else "circle"
        grafo.node(estado, shape=forma)

    grafo.edge("inicio", automata["inicial"])

    # Agrupar aristas paralelas evita cientos de flechas de letras en el AFD.
    grupos = {}
    for t in automata["transiciones"]:
        grupos.setdefault((t["origen"], t["destino"]), []).append(t["simbolo"])
    for (origen, destino), simbolos in grupos.items():
        grafo.edge(origen, destino, label=nohtml("\n".join("␠" if s == " " else s for s in sorted(set(simbolos)))), fontsize="13")

    contenido = grafo.pipe(format=formato)
    if formato == "svg":
        return "<svg" + contenido.decode("utf-8").split("<svg", 1)[1]
    return contenido


def construir_modelos(token, expresion, literal=False):
    directo = literal or (token in CONSTRUCCIONES_DIRECTAS and expresion == EXPRESIONES[token])
    afnd = crear_literal(expresion) if literal else crear_directo(token) if directo else crear_afnd(expresion)
    afd = convertir_afd(afnd)
    minimo = minimizar_afd(afd)
    if directo:
        muertos = {e for e, grupo in afd["equivalencias"].items() if not grupo}
        muertos_minimos = {e for e, grupo in minimo["equivalencias"].items() if set(grupo) <= muertos}
        afd = sin_sumidero(afd, muertos)
        minimo = sin_sumidero(minimo, muertos_minimos)
    return afnd, afd, minimo


@lru_cache(maxsize=32)
def generar_token(token, expresion):
    afnd, afd, minimo = construir_modelos(token, expresion)
    return {
        "expresion": expresion,
        "ejemplos": EJEMPLOS.get(token, ([], [])),
        "afnd": afnd,
        "afd": afd,
        "afd_minimo": minimo,
        "quintupla_afnd": generar_quintupla(afnd),
        "quintupla_afd": generar_quintupla(afd),
        "quintupla_afd_minimo": generar_quintupla(minimo),
        "tabla_afnd": generar_tabla(afnd),
        "tabla_afd": generar_tabla(afd),
        "tabla_afd_minimo": generar_tabla(minimo),
        "imagen_afnd": dibujar_automata(afnd, titulo="AFND - " + token),
        "imagen_afd": dibujar_automata(afd, titulo="AFD - " + token),
        "imagen_afd_minimo": dibujar_automata(minimo, titulo="AFD mínimo - " + token)
    }


def generar_todos(nombres=None):
    if nombres is None:
        nombres = EXPRESIONES
    return {
        token: generar_token(token, EXPRESIONES[token])
        for token in nombres
    }


def etiqueta_simbolos(simbolos):
    """Agrupa solo caracteres consecutivos; ␠ representa un espacio literal."""
    caracteres = sorted(set(simbolos))
    if any(len(c) != 1 for c in caracteres):
        return ", ".join("␠" if c == " " else c for c in caracteres)
    partes = []
    i = 0
    while i < len(caracteres):
        j = i
        while (j + 1 < len(caracteres) and caracteres[j].isalnum()
               and caracteres[j + 1].isalnum()
               and ord(caracteres[j + 1]) == ord(caracteres[j]) + 1):
            j += 1
        if j - i >= 2:
            partes.append("[" + caracteres[i] + "-" + caracteres[j] + "]")
        else:
            partes.extend("␠" if c == " " else c for c in caracteres[i:j + 1])
        i = j + 1
    return ", ".join(partes)


def agrupar_columnas(automata, epsilon=False, tabla=None):
    """Dos símbolos comparten columna solo si coinciden en TODOS los estados."""
    if tabla is None:
        tabla = generar_tabla(automata)
    simbolos = obtener_alfabeto(automata) + (["ε"] if epsilon and any(t["simbolo"] == "ε" for t in automata["transiciones"]) else [])
    grupos = {}
    for simbolo in simbolos:
        firma = tuple(tuple(fila.get(simbolo, [])) for fila in tabla)
        # Epsilon siempre se muestra separadamente.
        clave = (simbolo == "ε", firma)
        grupos.setdefault(clave, []).append(simbolo)
    return [(etiqueta_simbolos(valores), valores) for valores in grupos.values()]


def crear_literal(texto):
    return {"estados": [f"q{i}" for i in range(len(texto) + 1)], "inicial": "q0",
            "finales": [f"q{len(texto)}"], "transiciones": [
                {"origen": f"q{i}", "simbolo": c, "destino": f"q{i+1}"} for i, c in enumerate(texto)]}


def exportar_jff(automata):
    """Serializa el modelo real: ε se escribe como <read/> en JFLAP."""
    estados = automata["estados"]
    if len(set(estados)) != len(estados) or automata["inicial"] not in estados or not set(automata["finales"]) <= set(estados):
        raise ValueError("Estados iniciales/finales inválidos")
    ids = {e: str(i) for i, e in enumerate(estados)}
    raiz = Element("structure"); SubElement(raiz, "type").text = "fa"
    contenido = SubElement(raiz, "automaton")
    for i, e in enumerate(estados):
        n = SubElement(contenido, "state", id=ids[e], name=e)
        SubElement(n, "x").text = str(80 + (i % 6) * 130)
        SubElement(n, "y").text = str(80 + (i // 6) * 130)
        if e == automata["inicial"]: SubElement(n, "initial")
        if e in automata["finales"]: SubElement(n, "final")
    for t in automata["transiciones"]:
        c = t["simbolo"]
        if t["origen"] not in ids or t["destino"] not in ids or (c != "ε" and len(c) != 1):
            raise ValueError("Cada transición debe consumir un símbolo o ε")
        if c != "ε" and not (ord(c) in (9, 10, 13) or 32 <= ord(c) <= 55295 or 57344 <= ord(c) <= 65533 or 65536 <= ord(c) <= 1114111):
            raise ValueError("Símbolo no representable en XML 1.0")
        n = SubElement(contenido, "transition")
        SubElement(n, "from").text = ids[t["origen"]]
        SubElement(n, "to").text = ids[t["destino"]]
        SubElement(n, "read").text = None if c == "ε" else c
    return tostring(raiz, encoding="utf-8", xml_declaration=True)
