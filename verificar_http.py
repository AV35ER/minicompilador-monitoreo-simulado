import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def solicitar(base, ruta="/", datos=None, tipo=None, origen=None, metodo=None):
    headers = {"Content-Type": tipo} if tipo else {}
    if origen:
        headers["Origin"] = origen
    peticion = Request(base.rstrip("/") + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urlopen(peticion, timeout=25) as respuesta:
            return respuesta.status, respuesta.read(), respuesta.headers
    except HTTPError as error:
        return error.code, error.read(), error.headers


def verificar(base, origen=None):
    for intento in range(30):
        try:
            estado, cuerpo, _ = solicitar(base, "/healthz")
            if estado == 200 and json.loads(cuerpo) == {"status": "ok"}:
                break
        except (URLError, TimeoutError, ValueError):
            pass
        if intento == 29:
            raise RuntimeError("La aplicación no está disponible")
        time.sleep(2)

    estado, cuerpo, _ = solicitar(base)
    assert estado == 200 and b'<form method="POST"' in cuerpo
    from clinica import EJEMPLO
    datos = urlencode({"texto": EJEMPLO}).encode()
    estado, cuerpo, headers = solicitar(base, datos=datos, tipo="application/x-www-form-urlencoded")
    assert estado == 200 and cuerpo.count(b"<svg") == 15
    assert b"STORE S01" in cuerpo and b"codigo-intermedio" in cuerpo
    assert headers["Cache-Control"] == "no-store"
    limite = "ClinicaPruebaMultipart"
    contenido = (
        f"--{limite}\r\nContent-Disposition: form-data; name=\"archivo\"; filename=\"prueba.txt\"\r\n"
        "Content-Type: text/plain\r\n\r\n" + "\ufeff" + EJEMPLO + "\r\n"
        + f"--{limite}--\r\n"
    ).encode("utf-8")
    estado, cuerpo, _ = solicitar(base, "/api/analizar", datos=contenido, tipo="multipart/form-data; boundary=" + limite, origen=origen)
    resultado = json.loads(cuerpo)
    assert estado == 200 and resultado["aceptado"] and not resultado["errores"]
    assert len(resultado["tokens"]) == 22 and resultado["html"].count("<svg") == 15
    assert resultado["salida"]["avisos"][0]["codigo"] == "A01"
    assert resultado["codigo"][0] == {"op": "PUSH", "arg": 28}
    assert resultado["registros"][0]["arbol"]["simbolo"] == "P"
    assert resultado["registros"][0]["traza"][-1]["accion"] == "aceptar"
    assert len(resultado["slr"]["estados"]) == 27 and not resultado["slr"]["conflictos"]
    for texto, fase in [(EJEMPLO.replace("S01", "S011"), "léxico"), (EJEMPLO.replace("= 28", "28"), "sintáctico"),
                        (EJEMPLO+" SI S01>26 ENTONCES AVISAR A99;", "semántico")]:
        estado, cuerpo, _ = solicitar(base, "/api/analizar", datos=urlencode({"texto": texto}).encode(), tipo="application/x-www-form-urlencoded")
        r = json.loads(cuerpo)
        assert estado == 200 and not r["aceptado"] and r["salida"] is None and r["simulacion"] is None and not r["codigo"]
        assert r["registros"][0]["fase"] == fase
    estado, cuerpo, _ = solicitar(base, "/api/analizar", datos=urlencode({"texto": EJEMPLO.replace("28", "20").replace("15", "80")}).encode(), tipo="application/x-www-form-urlencoded")
    falso = json.loads(cuerpo)
    assert estado == 200 and falso["aceptado"] and falso["salida"]["avisos"] == []
    assert 8 not in falso["simulacion"]["ejecutadas"]
    if origen:
        assert headers.get("Access-Control-Allow-Origin") in (None, origen)
        estado, _, headers = solicitar(base, "/api/analizar", origen=origen, metodo="OPTIONS")
        assert estado == 200 and "POST" in headers["Access-Control-Allow-Methods"]
    estado, _, _ = solicitar(base, "/static/no-existe.txt")
    assert estado == 404
    estado, _, _ = solicitar(base, datos=urlencode({"texto": " " * (1024 * 1024 + 1)}).encode(), tipo="application/x-www-form-urlencoded")
    assert estado == 413
    print("HTTP correcto: GET, POST, TXT UTF8/BOM, 27 estados SLR, árbol, atributos, código, VM, JSON, rechazo atómico por fase, cortocircuito, 15 SVG, cache, 404 y 413")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:10000")
    parser.add_argument("--origen")
    argumentos = parser.parse_args()
    verificar(argumentos.url, argumentos.origen)
