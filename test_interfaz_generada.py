"""Comprueba el HTML entregado por Flask, sin simular una revisión visual."""
import re
import json
import unittest
from html.parser import HTMLParser
from xml.etree.ElementTree import Element, SubElement

import app
import automatas


class LeerHTML(HTMLParser):
    def __init__(self, contenido):
        super().__init__(convert_charrefs=True)
        self.raiz = Element("documento")
        self.pila = [self.raiz]
        self.feed(contenido)

    def handle_starttag(self, tag, attrs):
        nodo = SubElement(self.pila[-1], tag, dict((k, v or "") for k, v in attrs))
        if tag not in {"meta", "input", "br", "hr", "link", "img"}:
            self.pila.append(nodo)

    def handle_startendtag(self, tag, attrs):
        SubElement(self.pila[-1], tag, dict((k, v or "") for k, v in attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.pila) - 1, 0, -1):
            if self.pila[i].tag == tag:
                del self.pila[i:]
                break

    def handle_data(self, data):
        nodo = self.pila[-1]
        if len(nodo):
            nodo[-1].tail = (nodo[-1].tail or "") + data
        else:
            nodo.text = (nodo.text or "") + data


def texto(nodo):
    return "".join(nodo.itertext()).strip()


def simbolos_etiqueta(etiqueta, alfabeto):
    """Decodifica las etiquetas visibles sin usar el agrupador del programa."""
    resultado = set()
    for parte in etiqueta.split(", "):
        if parte == "␠":
            resultado.add(" ")
        elif parte.startswith("["):
            resultado.update(c for c in alfabeto if re.fullmatch(parte, c))
        else:
            resultado.add(parte)
    return resultado


class InterfazGeneradaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datos = automatas.generar_todos()
        cliente = app.app.test_client()
        respuesta = cliente.post("/", data={"texto": app.EJEMPLO})
        assert respuesta.status_code == 200
        cls.pagina = LeerHTML(respuesta.get_data(as_text=True)).raiz

    def test_quince_graficos_tablas_y_quintuplas_del_html(self):
        for nombre, datos in self.datos.items():
            panel = self.pagina.find('.//div[@id="token-' + nombre + '"]')
            for tipo in ("afnd", "afd", "afd_minimo"):
                with self.subTest(token=nombre, tipo=tipo):
                    modelo = datos[tipo]
                    vista = panel.find('.//div[@data-tipo="' + tipo + '"]')
                    self.assertNotIn("hidden", vista.attrib)
                    self.assertIsNotNone(vista.find('.//div[@class="quintupla"]'))
                    detalles = vista.findall("details")
                    self.assertTrue(all("open" not in d.attrib for d in detalles if d.get("class") != "nodo-sintactico"))
                    quint = vista.find('.//div[@class="quintupla"]')
                    valores = [texto(n) for n in quint.findall("div")]
                    self.assertEqual(valores[0], ", ".join(modelo["estados"]))
                    self.assertEqual(valores[1], automatas.etiqueta_simbolos(automatas.obtener_alfabeto(modelo)))
                    self.assertEqual(valores[3], modelo["inicial"])
                    self.assertEqual(valores[4], ", ".join(modelo["finales"]))
                    alfabeto = set(automatas.obtener_alfabeto(modelo)) | {"ε"}
                    esperadas = set()
                    for t in modelo["transiciones"]:
                        for simbolo in simbolos_etiqueta(t["simbolo"], alfabeto):
                            esperadas.add((t["origen"], simbolo, t["destino"]))

                    svg = vista.find(".//svg")
                    nodos = svg.findall('.//g[@class="node"]')
                    self.assertEqual({texto(n.find("title")) for n in nodos}, set(modelo["estados"]) | {"inicio"})
                    for nodo in nodos:
                        estado = texto(nodo.find("title"))
                        if estado != "inicio":
                            self.assertEqual(len(nodo.findall("ellipse")), 2 if estado in modelo["finales"] else 1)
                    aristas = set()
                    iniciales = []
                    for arista in svg.findall('.//g[@class="edge"]'):
                        origen, destino = texto(arista.find("title")).split("->")
                        etiquetas = arista.findall("text")
                        if not etiquetas:
                            iniciales.append((origen, destino))
                        else:
                            for etiqueta in etiquetas:
                                self.assertEqual(len(texto(etiqueta)), 1)
                                simbolo = " " if texto(etiqueta) == "␠" else texto(etiqueta)
                                aristas.add((origen, simbolo, destino))
                    self.assertEqual(iniciales, [("inicio", modelo["inicial"])])
                    self.assertEqual(aristas, esperadas)

                    tabla = vista.find('.//div[@class="tabla-contenedor transiciones"]/table')
                    columnas = [texto(n) for n in tabla.findall("thead/tr/th")][1:]
                    filas = tabla.findall("tbody/tr")
                    self.assertEqual(len(filas), len(modelo["estados"]))
                    celdas_transiciones = set()
                    for fila, estado in zip(filas, modelo["estados"]):
                        celdas = [texto(n) for n in fila.findall("td")]
                        self.assertEqual(celdas[0].replace("→", "").replace("*", "").strip(), estado)
                        self.assertEqual("→" in celdas[0], estado == modelo["inicial"])
                        self.assertEqual("*" in celdas[0], estado in modelo["finales"])
                        for columna, celda in zip(columnas, celdas[1:]):
                            if celda != "∅":
                                for simbolo in simbolos_etiqueta(columna, alfabeto):
                                    for destino in celda.split(", "):
                                        celdas_transiciones.add((estado, simbolo, destino))
                    self.assertEqual(celdas_transiciones, esperadas)
                    individuales = vista.find('.//div[@class="tabla-contenedor simbolos-individuales"]/table')
                    self.assertEqual([[texto(c) for c in fila.findall("td")] for fila in individuales.findall("tbody/tr")], [[t["origen"], "␠" if t["simbolo"] == " " else t["simbolo"], t["destino"]] for t in modelo["transiciones"]])
                    self.assertIsNone(vista.find('details[@class="detalle-automata"]'))
                    self.assertIsNotNone(vista.find('div[@class="quintupla"]'))
                    self.assertIsNotNone(vista.find('div[@class="tabla-contenedor transiciones"]'))


    def test_jerarquia_salida_y_detalle_real(self):
        import clinica
        proceso = self.pagina.find('.//div[@id="proceso-interno"]')
        self.assertEqual([texto(n.find("h3")) for n in proceso.findall("section")], ["2. Análisis léxico", "3. Análisis sintáctico y semántico"])
        self.assertEqual(json.loads(texto(self.pagina.find('.//pre[@id="salida-json"]'))), clinica.compilar(clinica.EJEMPLO)["salida"])
        self.assertIn("PUSH 28", texto(self.pagina.find('.//pre[@id="codigo-intermedio"]')))
        detalles = self.pagina.findall(".//details")
        self.assertTrue(all("open" not in d.attrib for d in detalles if d.get("class") != "nodo-sintactico"))
        self.assertEqual(sum(texto(d.find("summary")) == "Detalles técnicos del análisis SLR(1)" for d in detalles), 1)
        self.assertIn("PUNTO_Y_COMA", texto(proceso))
        self.assertIn("Derivación por la izquierda del programa completo", texto(proceso))
        self.assertIn("Traza SLR(1) del programa completo", texto(proceso))
        self.assertNotIn("Traza SLR(1), línea", texto(proceso))
        self.assertEqual(clinica.compilar(clinica.EJEMPLO)["salida"]["avisos"][0]["descripcion"], "Revisión técnica simulada")
        self.assertIn("Revisión técnica simulada", texto(self.pagina.find('.//pre[@id="salida-json"]')))
        sensor = self.pagina.find('.//div[@id="token-SENSOR"]')
        self.assertIn("AFD mínimo: 4 estados", texto(sensor))
        exportar = self.pagina.find('.//details[@id="exportar-jflap"]')
        self.assertNotIn("open", exportar.attrib)
        enlaces = [n for n in self.pagina.findall(".//a") if n.get("href", "").startswith("/jflap/")]
        self.assertEqual(len(enlaces), 33)
        self.assertEqual(enlaces, exportar.findall(".//a"))
        self.assertTrue(all(texto(n) == "Descargar .jff" for n in enlaces))
        self.assertFalse(self.pagina.find('.//section[@id="analisis-lexico"]//table').findall(".//a"))
        self.assertNotIn("sumidero", texto(self.pagina))

        self.assertIn("hidden", self.pagina.find('.//div[@id="gramatica"]').attrib)
        self.assertIn("hidden", self.pagina.find('.//div[@class="arbol-oculto"]').attrib)
        sintaxis = self.pagina.find('.//section[@id="analisis-sintactico"]')
        self.assertNotIn("hidden", sintaxis.attrib)
        self.assertIn("27 estados LR(0); 0 conflictos.", texto(sintaxis.find("p")))
        arbol = self.pagina.find('.//div[@class="arbol"]')
        def revisar(nodo, nivel=0):
            if nodo.tag == "details":
                self.assertEqual("open" in nodo.attrib, nivel < 3 and nodo.get("data-simbolo") not in {"CARGA", "COMP"})
                self.assertTrue(texto(nodo.find("summary")))
                for hijo in nodo.find('div[@class="hijos-sintacticos"]'):
                    revisar(hijo, nivel + 1)
        revisar(arbol.find("details"))
        self.assertIn("CARGA — CARGAR S01 = 28;", texto(arbol))
        self.assertIn("COMP — S01 > 26", texto(arbol))
        def reconstruir(n):
            hijos = n.find('div[@class="hijos-sintacticos"]')
            dato = {"simbolo": n.get("data-simbolo"), "hijos": [] if hijos is None else [reconstruir(h) for h in hijos]}
            if n.get("data-lexema") is not None:
                dato["lexema"] = n.get("data-lexema")
            return dato
        self.assertEqual(reconstruir(arbol.find("details")), clinica.compilar(clinica.EJEMPLO)["registros"][0]["arbol"])




    def test_tablas_slr_y_hojas_conservan_todos_los_datos(self):
        import clinica
        r = clinica.compilar(clinica.EJEMPLO)
        slr = r["slr"]
        tablas = self.pagina.findall('.//table[@class="tabla-slr"]')
        self.assertEqual(len(tablas), 2)
        for tabla, columnas, filas in zip(tablas, [slr["terminales"] + ["$"], slr["no_terminales"]], [slr["acciones"], slr["saltos"]]):
            self.assertEqual([texto(c) for c in tabla.findall("thead/tr/th")], ["Estado"] + ["PYC" if c == "PUNTO_Y_COMA" else c for c in columnas])
            self.assertEqual(len(tabla.findall("tbody/tr")), len(slr["estados"]))
            for i, fila in enumerate(tabla.findall("tbody/tr")):
                self.assertEqual([texto(c) for c in fila.findall("td")], ["I"+str(i)] + [str(filas[i].get(c, "")) for c in columnas])
        hojas = self.pagina.findall('.//span[@class="hoja-sintactica"]')
        self.assertEqual([(h.get("data-simbolo"), h.get("data-lexema")) for h in hojas if h.get("data-lexema") is not None], [(t["token"], t["lexema"]) for t in r["tokens"]])
        def contar(n):
            return 1 + sum(contar(h) for h in n["hijos"])
        self.assertEqual(len(hojas) + len(self.pagina.findall('.//details[@class="nodo-sintactico"]')), contar(r["registros"][0]["arbol"]))
        detalles = {texto(d.find("summary")): d for d in self.pagina.findall(".//details")}
        for nombre in ["Ver código intermedio (14 instrucciones)", "Ver todos los lexemas (22)", "Ver comprobaciones semánticas"]:
            self.assertNotIn("open", detalles[nombre].attrib)
        self.assertEqual(len(detalles["Ver todos los lexemas (22)"].findall(".//tbody/tr")), 22)
        self.assertEqual(len(detalles["Ver comprobaciones semánticas"].findall(".//tbody/tr")), len(r["registros"][0]["atributos"]))
