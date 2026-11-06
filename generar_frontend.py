import shutil
from pathlib import Path

from flask import render_template
from app import app, EJEMPLO, EXPRESIONES, EJEMPLOS, GRAMATICA, LIMITE_ENTRADA, compilar, modelos_jflap
from clinica import DESCRIPCIONES, SENSORES, ACCIONES, LITERALES, LIMITES, PATRONES_TOKENS
from automatas import CONSTRUCCIONES_DIRECTAS, exportar_jff


def configuracion():
    return {"patrones_tokens": PATRONES_TOKENS, "expresiones": EXPRESIONES, "ejemplos": EJEMPLOS, "gramatica": GRAMATICA,
            "limite": LIMITE_ENTRADA, "limites": LIMITES, "descripciones": DESCRIPCIONES,
            "sensores": SENSORES, "acciones": ACCIONES, "literales": LITERALES,
            "orden_tokens": list(EXPRESIONES), "construcciones_directas": CONSTRUCCIONES_DIRECTAS}


def generar(destino=Path("netlify-public")):
    destino.mkdir(parents=True, exist_ok=True)
    with app.test_request_context("/"):
        pagina = render_template(
            "index.html", texto=EJEMPLO, tokens=[], errores=[], mensaje="",
            analizado=False, resultados={}, expresiones=EXPRESIONES, ejemplos=EJEMPLOS, descripciones=DESCRIPCIONES,
            modo_estatico=True, compilacion=compilar(""), sensores=SENSORES, acciones=ACCIONES, literales=LITERALES,
            configuracion_lenguaje=configuracion()
        )
    (destino / "index.html").write_text(pagina, encoding="utf-8")
    jflap = destino / "jflap"
    jflap.mkdir(exist_ok=True)
    for token in PATRONES_TOKENS:
        for tipo, modelo in zip(("afnd", "afd", "afd_minimo"), modelos_jflap(token)):
            (jflap / f"{token}-{tipo}.jff").write_bytes(exportar_jff(modelo))
    origen = Path(__file__).resolve().parent / "netlify-public"
    for nombre in ("motor.js", "vistas.js", "slr.js", "simulador.js", "clinica.js", "cliente.js"):
        if (origen / nombre).resolve() != (destino / nombre).resolve():
            shutil.copyfile(origen / nombre, destino / nombre)


if __name__ == "__main__":
    generar()
