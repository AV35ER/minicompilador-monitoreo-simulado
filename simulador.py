"""Máquina de pila independiente: recibe código intermedio, nunca texto fuente."""
from clinica import SENSORES, ACCIONES, LIMITES


def ejecutar(codigo):
    if not isinstance(codigo, list) or not codigo or len(codigo) > LIMITES["codigo"]:
        raise ValueError("Código vacío o demasiado extenso.")
    etiquetas = {}
    binarios = {"GT": lambda a, b: a > b, "LT": lambda a, b: a < b,
                "GE": lambda a, b: a >= b, "LE": lambda a, b: a <= b,
                "EQ": lambda a, b: a == b, "NE": lambda a, b: a != b}
    for i, c in enumerate(codigo):
        if not isinstance(c, dict):
            raise ValueError("Instrucción intermedia inválida.")
        op, arg = c.get("op"), c.get("arg")
        if not isinstance(op, str):
            raise ValueError("Instrucción intermedia inválida.")
        if op in binarios:
            valido = set(c) == {"op"}
        elif op == "PUSH":
            valido = type(arg) is int and 0 <= arg <= 100
        elif op in ("LOAD", "STORE"):
            valido = isinstance(arg, str) and arg in SENSORES
        elif op == "EMIT":
            valido = isinstance(arg, str) and arg in ACCIONES
        elif op in ("LABEL", "JUMP_IF_FALSE"):
            valido = isinstance(arg, str) and bool(arg)
        else:
            valido = False
        if not valido or set(c) != ({"op"} if op in binarios else {"op", "arg"}):
            raise ValueError("Instrucción intermedia inválida.")
        if op == "LABEL":
            if arg in etiquetas:
                raise ValueError("Etiqueta duplicada.")
            etiquetas[arg] = i
    for i, c in enumerate(codigo):
        if c["op"] == "JUMP_IF_FALSE" and (c["arg"] not in etiquetas or etiquetas[c["arg"]] <= i):
            raise ValueError("Salto desconocido o no progresivo.")
    pila, memoria, avisos, ejecutadas, pc = [], {}, [], [], 0
    while pc < len(codigo):
        if len(ejecutadas) >= LIMITES["codigo"]:
            raise ValueError("Límite de ejecución excedido.")
        c = codigo[pc]
        op, arg = c["op"], c.get("arg")
        ejecutadas.append(pc)
        if op == "PUSH":
            pila.append(arg)
        elif op == "LOAD":
            if arg not in memoria:
                raise ValueError("Sensor sin inicializar.")
            pila.append(memoria[arg])
        elif op in binarios:
            if len(pila) < 2 or any(type(v) is not int for v in pila[-2:]):
                raise ValueError("Pila numérica inválida.")
            b, a = pila.pop(), pila.pop()
            pila.append(binarios[op](a, b))
        elif op == "STORE":
            if not pila or type(pila[-1]) is not int or not SENSORES[arg]["minimo"] <= pila[-1] <= SENSORES[arg]["maximo"]:
                raise ValueError("Asignación intermedia inválida.")
            memoria[arg] = pila.pop()
        elif op == "JUMP_IF_FALSE":
            if not pila or type(pila[-1]) is not bool:
                raise ValueError("Condición intermedia inválida.")
            if not pila.pop():
                pc = etiquetas[arg]
                continue
        elif op == "EMIT":
            avisos.append({"codigo": arg, "descripcion": ACCIONES[arg]})
        pc += 1
    if pila:
        raise ValueError("Pila final no vacía.")
    return {"memoria": memoria, "avisos": avisos, "pasos": len(ejecutadas), "ejecutadas": ejecutadas}
