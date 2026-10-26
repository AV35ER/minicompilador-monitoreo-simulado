"""Generador SLR(1) y parser por desplazamientos/reducciones, reutilizados."""
def generar_slr(gramatica):
    inicial = gramatica["inicial"]
    simbolos = {s for izquierda, derecha in gramatica["producciones"] for s in [izquierda, *derecha]}
    aumentado = inicial + "'"
    while aumentado in simbolos:
        aumentado += "'"
    producciones = [[aumentado, [inicial]], *gramatica["producciones"]]
    no_terminales = list(dict.fromkeys(p[0] for p in producciones))
    terminales = list(dict.fromkeys(s for _, derecha in producciones for s in derecha if s not in no_terminales))
    primeros = {s: {s} for s in terminales}
    primeros.update({s: set() for s in no_terminales})

    def primero(secuencia):
        resultado = set()
        for simbolo in secuencia:
            resultado.update(primeros[simbolo] - {"ε"})
            if "ε" not in primeros[simbolo]:
                return resultado
        return resultado | {"ε"}

    cambio = True
    while cambio:
        cambio = False
        for izquierda, derecha in producciones:
            nuevos = primero(derecha) - primeros[izquierda]
            primeros[izquierda].update(nuevos)
            cambio |= bool(nuevos)
    siguientes = {s: set() for s in no_terminales}
    siguientes[aumentado].add("$")
    cambio = True
    while cambio:
        cambio = False
        for izquierda, derecha in producciones:
            for i, simbolo in enumerate(derecha):
                if simbolo not in siguientes:
                    continue
                sufijo = primero(derecha[i + 1:])
                nuevos = (sufijo - {"ε"}) | (siguientes[izquierda] if "ε" in sufijo else set())
                nuevos -= siguientes[simbolo]
                siguientes[simbolo].update(nuevos)
                cambio |= bool(nuevos)

    def cierre(items):
        resultado = set(items)
        cambio = True
        while cambio:
            cambio = False
            for numero, punto in list(resultado):
                derecha = producciones[numero][1]
                if punto < len(derecha):
                    for j, (izquierda, _) in enumerate(producciones):
                        if izquierda == derecha[punto] and (j, 0) not in resultado:
                            resultado.add((j, 0))
                            cambio = True
        return tuple(sorted(resultado))

    estados = [cierre([(0, 0)])]
    nombres = {estados[0]: 0}
    transiciones = []
    for estado in estados:
        origen = nombres[estado]
        for simbolo in terminales + no_terminales[1:]:
            items = [(p, d + 1) for p, d in estado if d < len(producciones[p][1]) and producciones[p][1][d] == simbolo]
            if not items:
                continue
            destino = cierre(items)
            if destino not in nombres:
                nombres[destino] = len(estados)
                estados.append(destino)
            transiciones.append({"origen": origen, "simbolo": simbolo, "destino": nombres[destino]})
    acciones = [{} for _ in estados]
    saltos = [{} for _ in estados]

    def accion(estado, simbolo, valor):
        anterior = acciones[estado].get(simbolo)
        if anterior is not None and anterior != valor:
            raise ValueError(f"Conflicto SLR en I{estado}, {simbolo}: {anterior} / {valor}")
        acciones[estado][simbolo] = valor

    for t in transiciones:
        if t["simbolo"] in terminales:
            accion(t["origen"], t["simbolo"], "d" + str(t["destino"]))
        else:
            saltos[t["origen"]][t["simbolo"]] = t["destino"]
    for i, estado in enumerate(estados):
        for p, punto in estado:
            izquierda, derecha = producciones[p]
            if punto == len(derecha):
                for simbolo in (["$"] if p == 0 else sorted(siguientes[izquierda])):
                    accion(i, simbolo, "aceptar" if p == 0 else "r" + str(p))
    return {"inicial": inicial, "producciones": producciones, "terminales": terminales,
            "no_terminales": no_terminales[1:], "estados": estados, "transiciones": transiciones,
            "primeros": {s: sorted(primeros[s]) for s in no_terminales[1:]},
            "siguientes": {s: sorted(siguientes[s]) for s in no_terminales[1:]},
            "acciones": acciones, "saltos": saltos, "conflictos": []}


def derivar(arbol):
    frontera = [arbol]
    pasos = [[arbol["simbolo"]]]
    while any("lexema" not in n for n in frontera):
        i = next(i for i, n in enumerate(frontera) if "lexema" not in n)
        frontera[i:i + 1] = frontera[i]["hijos"]
        pasos.append([n["simbolo"] for n in frontera])
    return pasos


def analizar_sintaxis(tokens, modelo, reducir=None):
    pila, nodos, valores, traza, pos = [0], [], [], [], 0
    while True:
        simbolo = tokens[pos]["token"] if pos < len(tokens) else "$"
        accion = modelo["acciones"][pila[-1]].get(simbolo)
        traza.append({"pila": pila[:], "entrada": [t["token"] for t in tokens[pos:]] + ["$"], "accion": accion or "error"})
        if not accion:
            esperados = sorted(modelo["acciones"][pila[-1]])
            columna = tokens[pos]["columna"] if pos < len(tokens) else (tokens[-1]["columna"] + len(tokens[-1]["lexema"]) if tokens else 1)
            return {"aceptado": False, "arbol": None, "derivacion": [], "traza": traza,
                    "errores_sintacticos": [{"linea": tokens[pos]["linea"] if pos < len(tokens) else (tokens[-1]["linea"] if tokens else 1), "columna": columna, "lexema": tokens[pos]["lexema"] if pos < len(tokens) else "$", "detalle": "Se esperaba " + ", ".join(esperados) + "; se recibió " + simbolo + ".", "esperados": esperados}]}
        if accion == "aceptar":
            return {"aceptado": True, "arbol": nodos[0], "derivacion": derivar(nodos[0]), "traza": traza, "errores_sintacticos": [], "estructura": valores[0] if reducir else None}
        numero = int(accion[1:])
        if accion[0] == "d":
            nodos.append({"simbolo": simbolo, "lexema": tokens[pos]["lexema"], "hijos": []})
            valores.append(tokens[pos])
            pila.append(numero)
            pos += 1
        else:
            izquierda, derecha = modelo["producciones"][numero]
            hijos = nodos[-len(derecha):] if derecha else []
            argumentos = valores[-len(derecha):] if derecha else []
            if derecha:
                del nodos[-len(derecha):]
                del pila[-len(derecha):]
                del valores[-len(derecha):]
            valores.append(reducir(izquierda, argumentos) if reducir else None)
            nodos.append({"simbolo": izquierda, "hijos": hijos})
            pila.append(modelo["saltos"][pila[-1]][izquierda])
