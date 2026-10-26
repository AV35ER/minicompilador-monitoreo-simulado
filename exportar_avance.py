"""Exporta evidencia académica calculada, sin modificar el Word externo."""
from pathlib import Path
import hashlib
import json
from automatas import EXPRESIONES, EJEMPLOS, generar_todos
from app import preparar_tabla
from clinica import EJEMPLO, compilar, SENSORES, ACCIONES


def exportar(carpeta=Path("docs")):
    carpeta.mkdir(parents=True, exist_ok=True)
    figuras = carpeta / "figuras"
    figuras.mkdir(exist_ok=True)
    # Las figuras médicas anteriores están verificadas y conservadas en el histórico.
    historico = carpeta / "historico/citas-medicas/docs/figuras"
    actuales = {n.lower()+"-"+t+".svg" for n in EXPRESIONES for t in ("afnd", "afd", "afd_minimo")}
    for figura in figuras.glob("*.svg"):
        copia = historico / figura.name
        if figura.name not in actuales and copia.is_file():
            if hashlib.sha256(figura.read_bytes()).digest() != hashlib.sha256(copia.read_bytes()).digest():
                raise ValueError("Figura histórica modificada; no se elimina: " + figura.name)
            figura.unlink()
    r = compilar(EJEMPLO)
    (carpeta / "slr-generado.json").write_text(json.dumps(r["slr"], ensure_ascii=False, indent=2), encoding="utf-8")
    (carpeta / "ejemplo-compilado.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    lineas = ["# Diseño y desarrollo del minicompilador clínico", "",
        "## 1. Análisis", "",
        "Se simula la supervisión técnica de equipos ficticios de una clínica. El lenguaje codificado asigna parámetros, evalúa reglas y solicita avisos operativos. No diagnostica pacientes ni controla hardware.", "",
        "El analizador de citas previo reconocía datos ya interpretables. Esta evolución incorpora traducción a código intermedio y una máquina de pila independiente. Las fuentes y pruebas anteriores permanecen en `historico/citas-medicas`.", "",
        "La metodología en cascada separa análisis del lenguaje, diseño formal, implementación y pruebas. No se presentan estadísticas de una clínica ni se reutilizan como evidencia los antecedentes sobre citas. La revisión de literatura y la formulación investigativa deben actualizarse en el informe final.", "",
        "### Lenguaje y proceso", "",
        "Entrada codificada → léxico → SLR(1) → semántica → código de pila → simulación → JSON.", "",
        "```text", EJEMPLO, "```", "",
        "Se exige al menos una CARGA y una REGLA; cargas antes de reglas, terminación `;`, mayúsculas exactas, códigos conocidos, cargas únicas y referencias cargadas. Cualquier error impide toda ejecución. Una condición falsa es válida.", "",
        "| Token principal | Expresión regular |", "|---|---|"]
    lineas += [f"| {n} | `{p.replace('|', chr(92)+'|')}` |" for n, p in EXPRESIONES.items()]
    lineas += ["", "Literales adicionales: CARGAR, SI, Y, ENTONCES, AVISAR y PUNTO_Y_COMA (`;`). No forman parte de las cinco familias seleccionables, pero sí del inventario léxico.", "",
        "Los códigos S99 y A99 son lexemas válidos y semánticamente desconocidos. S011, SIEMPRE y ! aislado no se fragmentan para aceptarlos.", "",
        "### Diccionario semántico", ""]
    lineas += [f"- {n}: {s['descripcion']}, entero {s['minimo']}–{s['maximo']}." for n, s in SENSORES.items()]
    lineas += [f"- {n}: {s}." for n, s in ACCIONES.items()]
    lineas += ["", "Rangos ficticios académicos, sin significado clínico real. Se comprueban cargas y umbrales. Los ceros iniciales son válidos y se traducen a un entero decimal.", "",
        "## 2. Diseño", "", "### Arquitectura", "",
        "`automatas.py`/`motor.js` reconocen las cinco familias mediante construcciones directas; conservan Thompson como motor general. `slr.py`/`slr.js` calculan FIRST/FOLLOW, cerraduras LR(0), ACTION/GOTO y reducciones. `clinica.py`/`clinica.js` implementan el nuevo lenguaje, sus atributos y traducción. `simulador.py`/`simulador.js` ejecutan únicamente código de pila. Flask conserva rutas/TXT; Netlify usa seis scripts locales sin Render.", "",
        "### Gramática aumentada y tabla SLR(1)", "",
        f"Se calcularon {len(r['slr']['estados'])} estados LR(0) y {len(r['slr']['conflictos'])} conflictos SLR(1). PYC abrevia PUNTO_Y_COMA. La producción aumentada 0 se presenta fuera de P.", ""]
    for i, (izq, der) in enumerate(r["slr"]["producciones"]):
        lineas.append(f"{i}. `{izq} → {' '.join(der) or 'ε'}`")
    lineas += ["", "La evidencia completa generada está en [slr-generado.json](slr-generado.json): items, transiciones, FIRST, FOLLOW y ACTION/GOTO. El árbol, las derivaciones, la traza y los atributos del ejemplo están en [ejemplo-compilado.json](ejemplo-compilado.json).", "",
        "### Autómatas, quíntuplas y tablas", "",
        "Un AFD parcial es un caso particular de AFND. Las construcciones directas no inventan diferencias entre ambos. La conversión por subconjuntos y la minimización se ejecutan realmente; el sumidero interno se omite en la representación parcial. Una transición inexistente significa rechazo. El AFD mínimo de SENSOR tiene cuatro estados bajo la convención de autómata parcial, sin sumidero explícito (δ: Q × Σ ⇀ Q). Esta cifra no describe un AFD total.", ""]
    for nombre, datos in generar_todos().items():
        lineas += ["### " + nombre, "", "Regex: `"+datos["expresion"]+"`.", "",
                   "Ejemplos léxicos: " + ", ".join(EJEMPLOS[nombre][0]) + ".", ""]
        for tipo in ("afnd", "afd", "afd_minimo"):
            archivo = nombre.lower()+"-"+tipo+".svg"
            (figuras / archivo).write_text(datos["imagen_"+tipo], encoding="utf-8")
            q, modelo = datos["quintupla_"+tipo], datos[tipo]
            lineas += [f"#### {'AFD mínimo parcial, sin sumidero explícito' if tipo == 'afd_minimo' else tipo.upper()} ({len(modelo['estados'])} estados)", "", f"![{nombre} {tipo}](figuras/{archivo})", "",
                       f"M=(Q, Σ, δ, q₀, F); Q={q['Q']}; Σ={q['Sigma']}; q₀={q['q0']}; F={q['F']}.", ""]
            tabla = preparar_tabla(modelo, tipo == "afnd")
            lineas += ["| Estado | " + " | ".join(tabla["alfabeto"]) + " |", "|---|"+"---|"*len(tabla["alfabeto"])]
            lineas += ["| "+("→" if f["inicial"] else "")+("*" if f["final"] else "")+f["estado"]+" | "+" | ".join(f["destinos"][s] for s in tabla["alfabeto"])+" |" for f in tabla["filas"]]
            lineas.append("")
    lineas += ["## 3. Desarrollo", "",
        "Las reducciones sintetizan listas ordenadas de cargas, reglas y comparaciones. Solo después de validar todo el programa se emite PUSH/STORE/LOAD, comparadores, JUMP_IF_FALSE, EMIT y LABEL. Cada comparación falsa salta al final de su regla, implementando Y con cortocircuito.", "",
        "### Código calculado del ejemplo", "", "```text"]
    lineas += [x["op"]+(" "+str(x["arg"]) if "arg" in x else "") for x in r["codigo"]]
    lineas += ["```", "", "### Salida de la ejecución", "", "```json", json.dumps(r["salida"], ensure_ascii=False, indent=2), "```", "",
        "## 4. Pruebas y entrega", "",
        "Las herramientas son unittest, node:test, comparación exhaustiva por producto de autómatas, comparación JSON Python/JavaScript, lectura estructural de SVG y prueba de build limpio con red bloqueada en el frontend. Las comprobaciones reproducibles están implementadas en `test_proyecto.py`, `test_paridad.py`, `test_interfaz_generada.py`, `test_despliegue.py`, `test_cliente.cjs` y `verificar_http.py`, en la raíz del proyecto.", "",
        "El PowerPoint pide un reporte PDF. La interfaz ofrece imprimir/guardar PDF con el navegador; esta operación y el aspecto en escritorio/móvil requieren revisión manual. No se presenta un DOM simulado como revisión visual.", "",
        "El documento Word externo no se editó ni se renderizó: este contenido Markdown está preparado para incorporarlo y verificarlo visualmente. No se afirma aprobación formal del docente ni cierre de los requisitos investigativos del informe."]
    (carpeta / "avance-etapa-2.md").write_text("\n".join(lineas)+"\n", encoding="utf-8")


if __name__ == "__main__":
    exportar()
