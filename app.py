
import os
from graphviz import ExecutableNotFound, CalledProcessError
from flask import Flask, abort, render_template, request
from automatas import EXPRESIONES, EJEMPLOS, generar_todos, generar_tabla, agrupar_columnas, etiqueta_simbolos

from clinica import EJEMPLO, GRAMATICA, DESCRIPCIONES, analizar, compilar, tabla_slr, SENSORES, ACCIONES, LITERALES

app = Flask(__name__)
app.json.ensure_ascii = False
app.jinja_env.filters["simbolos"] = etiqueta_simbolos
LIMITE_ENTRADA = 1024 * 1024
app.config.update(
    MAX_CONTENT_LENGTH=2 * LIMITE_ENTRADA + 64 * 1024,
    MAX_FORM_MEMORY_SIZE=LIMITE_ENTRADA + 64 * 1024,
    MAX_FORM_PARTS=10
)

def preparar_tabla(automata, es_afnd, tabla=None):
    if tabla is None:
        tabla = generar_tabla(automata)
    grupos = agrupar_columnas(automata, es_afnd, tabla)
    filas = []
    for fila in tabla:
        estado = fila["estado"]
        filas.append({
            "estado": estado,
            "inicial": estado == automata["inicial"],
            "final": estado in automata["finales"],
            "destinos": {
                etiqueta: ", ".join(fila.get(simbolos[0], [])) or "∅"
                for etiqueta, simbolos in grupos
            }
        })
    return {"alfabeto": [g[0] for g in grupos], "grupos": grupos, "filas": filas}


def preparar_resultados():
    resultados = {}
    for nombre, datos in generar_todos().items():
        resultados[nombre] = {
            **datos,
            "tabla_visual_afnd": preparar_tabla(datos["afnd"], True, datos["tabla_afnd"]),
            "tabla_visual_afd": preparar_tabla(datos["afd"], False, datos["tabla_afd"]),
            "tabla_visual_afd_minimo": preparar_tabla(datos["afd_minimo"], False, datos["tabla_afd_minimo"])
        }

    return resultados


@app.route("/", methods=["GET", "POST"])
@app.route("/api/analizar", methods=["POST"])
def inicio():
    texto = EJEMPLO
    tokens = []
    errores = []
    mensaje = ""
    analizado = False
    resultados = {}
    compilacion = compilar("")

    if request.method == "POST":
        texto = request.form.get("texto", "")
        archivo = request.files.get("archivo")

        if archivo and archivo.filename:
            if not archivo.filename.lower().endswith(".txt"):
                mensaje = "Selecciona un archivo TXT."
            else:
                try:
                    contenido = archivo.read(LIMITE_ENTRADA + 1)
                    if len(contenido) > LIMITE_ENTRADA:
                        abort(413)
                    texto = contenido.decode("utf-8-sig")
                except UnicodeDecodeError:
                    mensaje = "El archivo debe estar guardado en UTF-8."

        if not mensaje:
            if len(texto.encode("utf-8")) > LIMITE_ENTRADA:
                abort(413)
            if texto.strip():
                compilacion = compilar(texto)
                tokens, errores = compilacion["tokens"], compilacion["errores"]
                analizado = True
                try:
                    resultados = preparar_resultados()
                except (ExecutableNotFound, CalledProcessError):
                    mensaje = (
                        "No se pudieron generar los gráficos. Comprueba que Graphviz "
                        "esté instalado y que el comando dot esté disponible en PATH."
                    )
            else:
                mensaje = "Escribe instrucciones o carga un archivo TXT."

    if request.path == "/api/analizar":
        return {
            "html": render_template(
                "resultados.html", tokens=tokens, errores=errores,
                analizado=analizado, resultados=resultados,
                compilacion=compilacion, expresiones=EXPRESIONES, ejemplos=EJEMPLOS, descripciones=DESCRIPCIONES, literales=LITERALES
            ),
            "mensaje": mensaje,
            "texto": texto,
            "tokens": tokens,
            "errores": errores,
            "registros": compilacion["registros"], "aceptado": compilacion["aceptado"], "slr": compilacion["slr"],
            "salida": compilacion["salida"], "codigo": compilacion["codigo"], "simulacion": compilacion["simulacion"], "correspondencias": compilacion["correspondencias"]
        }, 503 if analizado and mensaje else 400 if mensaje else 200

    return render_template(
        "index.html",
        texto=texto,
        tokens=tokens,
        errores=errores,
        mensaje=mensaje,
        analizado=analizado,
        resultados=resultados,
        expresiones=EXPRESIONES, ejemplos=EJEMPLOS, descripciones=DESCRIPCIONES,
        compilacion=compilacion, sensores=SENSORES, acciones=ACCIONES, literales=LITERALES
    )


@app.get("/healthz")
def salud():
    return {"status": "ok"}


@app.after_request
def configurar_cache(respuesta):
    if request.endpoint != "static":
        respuesta.headers["Cache-Control"] = "no-store"
    origen = request.headers.get("Origin")
    permitidos = {valor.strip() for valor in os.environ.get("CORS_ORIGINS", "").split(",") if valor.strip()}
    if request.path in ("/api/analizar", "/healthz"):
        respuesta.vary.add("Origin")
        if origen in permitidos:
            respuesta.headers["Access-Control-Allow-Origin"] = origen
            respuesta.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            respuesta.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return respuesta


@app.errorhandler(413)
def archivo_grande(error):
    if request.path == "/api/analizar":
        return {"mensaje": "La entrada supera el máximo de 1 MiB."}, 413
    return "El archivo supera el máximo de 1 MiB.", 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))
