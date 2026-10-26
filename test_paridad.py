"""Compara los algoritmos de ambos lenguajes y un build sin archivos locales."""
import json
import os
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Thread
from tempfile import TemporaryDirectory
import unittest
from urllib.request import urlopen
from xml.etree import ElementTree

import app
import automatas
import clinica
from generar_frontend import configuracion
from test_interfaz_generada import LeerHTML, texto


@unittest.skipUnless(shutil.which("node"), "La paridad JavaScript requiere Node")
class ParidadTests(unittest.TestCase):
    def ejecutar_node(self, codigo, datos):
        resultado = subprocess.run(["node", "-e", codigo], input=json.dumps(datos),
                                   text=True, encoding="utf-8", capture_output=True, timeout=60)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        return json.loads(resultado.stdout)

    def test_modelos_tablas_y_quintuplas_identicos(self):
        expresiones = list(automatas.EXPRESIONES.values()) + [
            "a+", "a*", "(a|b)*abb", "a?b{1,3}", "[a-c]{0,2}", "x{2,}", "", "a|", r"\+", "(ab|c)+"]
        datos = self.ejecutar_node("""
            const fs = require('node:fs'), m = require('./netlify-public/motor.js');
            const patrones = JSON.parse(fs.readFileSync(0, 'utf8'));
            console.log(JSON.stringify(patrones.map(p => {
                const afnd=m.crearAFND(p), afd=m.convertirAFD(afnd), minimo=m.minimizarAFD(afd);
                return [afnd,afd,minimo].map((a,i) => [a,m.quintupla(a),m.tabla(a),m.tablaVisual(a,i===0)]);
            })));
        """, expresiones)
        for patron, resultado in zip(expresiones, datos):
            afnd = automatas.crear_afnd(patron)
            afd = automatas.convertir_afd(afnd)
            for i, a in enumerate([afnd, afd, automatas.minimizar_afd(afd)]):
                with self.subTest(patron=patron, tipo=i):
                    esperado = [a, automatas.generar_quintupla(a), automatas.generar_tabla(a), app.preparar_tabla(a, i == 0)]
                    self.assertEqual(resultado[i], json.loads(json.dumps(esperado)))

    def test_programas_completos_identicos(self):
        from test_proyecto import casos
        from generar_frontend import configuracion
        programas = casos()
        for op in [">", "<", ">=", "<=", "==", "!="]:
            programas.extend(f"CARGAR S01={v}; SI S01 {op} {u} ENTONCES AVISAR A01;" for v in [0, 20, 28, 50, 51] for u in [0, 26, 50, 51])
        programas.extend([app.EJEMPLO.replace("\n", "\r\n"), app.EJEMPLO.replace(" ", "\t"), "\x1f\u0085", app.EJEMPLO+" SI S01>0 ENTONCES AVISAR A02;"])
        datos = self.ejecutar_node("""
            const fs=require('node:fs'),c=require('./netlify-public/clinica.js');
            const datos=JSON.parse(fs.readFileSync(0,'utf8'));
            console.log(JSON.stringify(datos.programas.map(p=>c.compilar(p,datos.config))));
        """, {"programas": programas, "config": configuracion()})
        self.assertEqual(len(datos), len(programas))
        for programa, resultado in zip(programas, datos):
            with self.subTest(programa=programa[:80]):
                self.assertEqual(resultado, json.loads(json.dumps(app.compilar(programa))))

    def test_gramaticas_slr_generadas_identicas(self):
        gramaticas = [app.GRAMATICA,
                      {"inicial": "S", "producciones": [["S", ["A", "b"]], ["A", []], ["A", ["a"]]]},
                      {"inicial": "S", "producciones": [["S", ["S'"]], ["S'", ["a"]]]},
                      {"inicial": "S", "producciones": [["S", ["S", "a"]], ["S", ["b"]]]}]
        resultados = self.ejecutar_node("""
            const fs=require('node:fs'), c=require('./netlify-public/clinica.js');
            console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(c.generarSLR)));
        """, gramaticas)
        self.assertEqual(resultados, json.loads(json.dumps([clinica.generar_slr(g) for g in gramaticas])))

    def test_html_estatico_graficos_tablas_quintuplas(self):
        datos = self.ejecutar_node("""
            const fs=require('node:fs'), m=require('./netlify-public/motor.js'), v=require('./netlify-public/vistas.js'), c=require('./netlify-public/clinica.js');
            const config=JSON.parse(fs.readFileSync(0,'utf8'));
            const automatas=m.generarTodos(config);
            console.log(JSON.stringify({html:v.renderizar(c.compilar(config.ejemplo,config),automatas,config),automatas}));
        """, {**configuracion(), "ejemplo": app.EJEMPLO})
        pagina = LeerHTML(datos["html"]).raiz
        compilacion = clinica.compilar(app.EJEMPLO)
        def reconstruir_arbol(n):
            hijos = n.find('div[@class="hijos-sintacticos"]')
            dato = {"simbolo": n.get("data-simbolo"), "hijos": [] if hijos is None else [reconstruir_arbol(h) for h in hijos]}
            if n.get("data-lexema") is not None:
                dato["lexema"] = n.get("data-lexema")
            return dato
        self.assertEqual(reconstruir_arbol(pagina.find('.//div[@class="arbol"]/details')), compilacion["registros"][0]["arbol"])
        self.assertIn("CARGA — CARGAR S01 = 28;", texto(pagina.find('.//div[@class="arbol"]')))
        self.assertIn("hidden", pagina.find('.//div[@id="gramatica"]').attrib)
        self.assertIn("hidden", pagina.find('.//div[@class="arbol-oculto"]').attrib)
        sintaxis = pagina.find('.//section[@id="analisis-sintactico"]')
        self.assertNotIn("hidden", sintaxis.attrib)
        self.assertIn("27 estados LR(0); 0 conflictos.", texto(sintaxis.find("p")))
        tablas_slr = pagina.findall('.//table[@class="tabla-slr"]')
        self.assertEqual(len(tablas_slr), 2)
        slr = compilacion["slr"]
        for tabla, columnas, filas in zip(tablas_slr, [slr["terminales"] + ["$"], slr["no_terminales"]], [slr["acciones"], slr["saltos"]]):
            self.assertEqual(len(tabla.findall("tbody/tr")), len(slr["estados"]))
            for i, fila in enumerate(tabla.findall("tbody/tr")):
                self.assertEqual([texto(c) for c in fila.findall("td")], ["I" + str(i)] + [str(filas[i].get(c, "")) for c in columnas])
        self.assertEqual([(n.get("data-simbolo"), n.get("data-lexema")) for n in pagina.findall('.//span[@class="hoja-sintactica"]') if n.get("data-lexema") is not None], [(t["token"], t["lexema"]) for t in compilacion["tokens"]])
        for d in pagina.findall(".//details"):
            if d.get("class") != "nodo-sintactico":
                self.assertNotIn("open", d.attrib)
        graficos = re.findall(r"<svg\b.*?</svg>", datos["html"], re.DOTALL)
        self.assertEqual(len(graficos), 15)
        for grafico in graficos:
            ElementTree.fromstring(grafico)
        for nombre, modelos in datos["automatas"].items():
            referencia = dict(zip(("afnd", "afd", "afd_minimo"), automatas.construir_modelos(nombre, automatas.EXPRESIONES[nombre])))
            for tipo in ("afnd", "afd", "afd_minimo"):
                referencia["quintupla_" + tipo] = automatas.generar_quintupla(referencia[tipo])
                referencia["tabla_" + tipo] = automatas.generar_tabla(referencia[tipo])
            for tipo in ("afnd", "afd", "afd_minimo"):
                with self.subTest(token=nombre, tipo=tipo):
                    modelo = modelos[tipo]
                    self.assertEqual(modelo, json.loads(json.dumps(referencia[tipo])))
                    self.assertEqual(modelos["quintupla_" + tipo], json.loads(json.dumps(referencia["quintupla_" + tipo])))
                    self.assertEqual(modelos["tabla_" + tipo], json.loads(json.dumps(referencia["tabla_" + tipo])))
                    panel = pagina.find(f'.//div[@id="token-{nombre}"]')
                    vista = panel.find(f'.//div[@data-tipo="{tipo}"]')
                    self.assertNotIn("hidden", vista.attrib)
                    self.assertIsNotNone(vista.find('div[@class="quintupla"]'))
                    detalles = vista.findall("details")
                    self.assertTrue(all("open" not in d.attrib for d in detalles))
                    quint = [texto(n) for n in vista.find('.//div[@class="quintupla"]').findall("div")]
                    q = modelos["quintupla_" + tipo]
                    self.assertEqual(quint, [", ".join(q["Q"]), automatas.etiqueta_simbolos(q["Sigma"]), "Ver tabla de transiciones.", q["q0"], ", ".join(q["F"])])
                    tabla = vista.find('.//div[@class="transiciones"]//table')
                    visual = modelos["tabla_visual_" + tipo]
                    self.assertEqual([texto(n) for n in tabla.findall("thead/tr/th")], ["Estado", *visual["alfabeto"]])
                    filas = tabla.findall("tbody/tr")
                    self.assertEqual(len(filas), len(visual["filas"]))
                    for fila, esperada in zip(filas, visual["filas"]):
                        self.assertEqual([texto(n) for n in fila.findall("td")][1:], [esperada["destinos"][s] for s in visual["alfabeto"]])
                    svg = vista.find(".//svg")
                    # Además de leer HTML, el SVG debe ser XML válido.
                    ElementTree.fromstring(ElementTree.tostring(svg, encoding="unicode"))
                    estados = svg.findall('.//g[@class="estado"]')
                    self.assertEqual([n.get("data-estado") for n in estados], modelo["estados"])
                    self.assertEqual([n.get("data-estado") for n in estados if n.get("data-inicial") == "true"], [modelo["inicial"]])
                    self.assertEqual([n.get("data-estado") for n in estados if n.get("data-final") == "true"], modelo["finales"])
                    aristas = []
                    for arista in svg.findall('.//g[@class="arista"]'):
                        simbolos = json.loads(arista.get("data-simbolos"))
                        self.assertEqual(texto(arista.find("text")), automatas.etiqueta_simbolos(simbolos))
                        self.assertTrue(arista.find("path").get("d"))
                        aristas.extend((arista.get("data-origen"), s, arista.get("data-destino")) for s in simbolos)
                    self.assertCountEqual(aristas, [(t["origen"], t["simbolo"], t["destino"]) for t in modelo["transiciones"]])

    def test_copia_limpia_build_y_flujo_generado_sin_red(self):
        with TemporaryDirectory() as carpeta:
            destino = Path(carpeta)
            # Solamente las fuentes del build y sus pruebas: sin .venv, Git ni HTML previo.
            for nombre in ("app.py", "automatas.py", "clinica.py", "slr.py", "simulador.py", "generar_frontend.py", "test_cliente.cjs"):
                shutil.copyfile(nombre, destino / nombre)
            shutil.copytree("templates", destino / "templates")
            (destino / "netlify-public").mkdir()
            for nombre in ("motor.js", "vistas.js", "slr.js", "simulador.js", "clinica.js", "cliente.js"):
                shutil.copyfile(Path("netlify-public", nombre), destino / "netlify-public" / nombre)
            env = {**os.environ, "NETLIFY": "true", "RENDER_API_URL": "", "PYTHONUTF8": "1"}
            build = subprocess.run([sys.executable, "generar_frontend.py"], cwd=destino, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertTrue((destino / "netlify-public/index.html").is_file())
            class ServidorSilencioso(SimpleHTTPRequestHandler):
                def log_message(self, formato, *args):
                    pass
            servidor = ThreadingHTTPServer(("127.0.0.1", 0), partial(ServidorSilencioso, directory=str(destino / "netlify-public")))
            hilo = Thread(target=servidor.serve_forever, daemon=True)
            hilo.start()
            try:
                for recurso in ("index.html", "motor.js", "vistas.js", "slr.js", "simulador.js", "clinica.js", "cliente.js"):
                    with urlopen(f"http://127.0.0.1:{servidor.server_port}/{recurso}", timeout=5) as respuesta:
                        self.assertEqual(respuesta.status, 200)
                        self.assertIn("html" if recurso.endswith(".html") else "javascript", respuesta.headers["Content-Type"])
                        self.assertEqual(respuesta.read(), (destino / "netlify-public" / recurso).read_bytes())
            finally:
                servidor.shutdown()
                servidor.server_close()
                hilo.join()
            pruebas = subprocess.run(["node", "--test", "test_cliente.cjs"], cwd=destino, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(pruebas.returncode, 0, pruebas.stdout + pruebas.stderr)


if __name__ == "__main__":
    unittest.main()
