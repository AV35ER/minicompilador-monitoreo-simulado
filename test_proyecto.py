"""Pruebas funcionales del lenguaje, la traducción y el simulador independiente."""
import copy
import itertools
import unittest
from collections import deque
import clinica as c
import automatas as a
from simulador import ejecutar
from slr import generar_slr, analizar_sintaxis


def programa(valor=28, comparador=">", umbral=26, accion="A01"):
    return f"CARGAR S01 = {valor}; SI S01 {comparador} {umbral} ENTONCES AVISAR {accion};"


def casos():
    return [c.EJEMPLO, c.EJEMPLO.replace("28", "20").replace("15", "80"), "", " ",
            "CARGAR S01 28; SI S01>26 ENTONCES AVISAR A01;", programa().replace("S01", "S99"),
            programa().replace("S01", "S011"), programa().replace("SI ", "SIEMPRE "),
            programa().replace(">", "!"), programa(51), programa(28, "<=", 50), programa(0, "==", 0),
            programa().replace("SI S01", "SI S02"), programa(28, accion="A99"),
            "CARGAR S01=28; CARGAR S01=20; SI S01>26 ENTONCES AVISAR A01;",
            programa()+" SI S01<30 ENTONCES AVISAR A02;", "😀 "+programa(),
            programa().replace("= 28", "= 1.5"), "\ufeff"+programa(),
            programa().replace("28", "0"*5000+"28"), programa().replace("28", "9"*400),
            " ".join(["CARGAR S01=28;"]*70), "x"*65537]


def acepta(modelo, texto):
    estados = a.cierre_epsilon([modelo["inicial"]], modelo["transiciones"])
    for simbolo in texto:
        estados = a.cierre_epsilon(a.mover(estados, simbolo, modelo["transiciones"]), modelo["transiciones"])
    return bool(set(estados) & set(modelo["finales"]))


class LenguajeTests(unittest.TestCase):
    def test_lexemas_literales_y_prioridad(self):
        tokens, errores = c.analizar("CARGAR S99=100; SI S99>=20 Y S01!=0 ENTONCES AVISAR A99;")
        self.assertFalse(errores)
        self.assertEqual([t["lexema"] for t in tokens if t["token"] == "COMPARADOR"], [">=", "!="])
        self.assertEqual(tokens[2]["token"], "IGUAL")
        self.assertEqual(tokens[4]["token"], "PUNTO_Y_COMA")
        self.assertEqual([t["lexema"] for t in c.analizar("===")[0]], ["==", "="])

    def test_no_fragmentacion_indebida(self):
        for texto in ["S011", "SIEMPRE", "!", "A010", "s01", "123x", "28.5", "__proto__"]:
            t, e = c.analizar(texto)
            self.assertEqual(t, [], texto)
            self.assertEqual(e[0]["lexema"], texto)

    def test_posiciones(self):
        t, e = c.analizar("CARGAR S01=28;\n  SIEMPRE S01>20;")
        self.assertEqual(e[0]["linea"], 2)
        self.assertEqual(e[0]["columna"], 3)
        self.assertEqual(t[1]["columna"], 8)

    def test_27_estados_y_cero_conflictos(self):
        slr = c.tabla_slr()
        self.assertEqual(len(slr["estados"]), 27)
        self.assertEqual(slr["conflictos"], [])
        self.assertIn("ε", slr["primeros"]["RESTO"])
        self.assertIn("ENTONCES", slr["siguientes"]["RESTO"])

    def test_arbol_y_reducciones_construyen_estructura(self):
        r = c.compilar(c.EJEMPLO)["registros"][0]
        def hojas(n):
            return [n["lexema"]] if "lexema" in n else [s for h in n["hijos"] for s in hojas(h)]
        self.assertEqual(hojas(r["arbol"]), [t["lexema"] for t in c.analizar(c.EJEMPLO)[0]])
        self.assertEqual(r["traza"][-1]["accion"], "aceptar")
        self.assertTrue(any(p["accion"].startswith("r") for p in r["traza"]))
        self.assertEqual([x["sensor"] for x in r["estructura"]["cargas"]], ["S01", "S02"])
        self.assertEqual([x["sensor"] for x in r["estructura"]["reglas"][0]["comparaciones"]], ["S01", "S02"])

    def test_restricciones_sintacticas(self):
        for texto in ["CARGAR S01=28;", "SI S01>26 ENTONCES AVISAR A01;", programa().replace("= 28", "28"),
                      programa()+" CARGAR S02=15;", programa().replace(";", "", 1), programa().replace("S01 > 26", "(S01 > 26)")]:
            r = c.compilar(texto)
            self.assertFalse(r["aceptado"], texto)
            self.assertIsNone(r["simulacion"])

    def test_rechazo_atomico_en_cada_fase(self):
        for texto, fase in [(programa()+" !", "léxico"), (programa()+" SI", "sintáctico"),
                            (programa()+" SI S01>26 ENTONCES AVISAR A99;", "semántico")]:
            r = c.compilar(texto)
            self.assertEqual(r["registros"][0]["fase"], fase)
            self.assertEqual(r["codigo"], [])
            self.assertIsNone(r["salida"])
            self.assertIsNone(r["simulacion"])

    def test_codigos_rangos_duplicados_referencias(self):
        for texto in [programa(51), programa(28, umbral=51), programa().replace("S01", "S99"),
                      programa(28, accion="A99"), programa().replace("SI S01", "SI S02"),
                      "CARGAR S01=20; "+programa(), programa().replace("28", "9"*100),
                      programa().replace("S01", "S02").replace("28", "101")]:
            r = c.compilar(texto)
            self.assertTrue(r["registros"][0]["sintaxis_aceptada"], texto)
            self.assertTrue(r["registros"][0]["errores_semanticos"], texto)
            self.assertIsNone(r["simulacion"])

    def test_limites_y_ceros_iniciales(self):
        self.assertTrue(c.compilar(programa().replace("28", "0"*5000+"28"))["aceptado"])
        for texto in ["x"*65537, " ".join(["CARGAR S01=1;"]*70)]:
            self.assertFalse(c.compilar(texto)["aceptado"])

    def test_generador_slr_general_y_conflictos(self):
        for gramatica in [{"inicial": "S", "producciones": [["S", ["A", "b"]], ["A", []], ["A", ["a"]]]},
                          {"inicial": "S", "producciones": [["S", ["S'"]], ["S'", ["a"]]]}]:
            modelo = generar_slr(gramatica)
            self.assertTrue(analizar_sintaxis([{"token": "a", "lexema": "a", "linea": 1, "columna": 1}] +
                ([{"token": "b", "lexema": "b", "linea": 1, "columna": 2}] if "A" in modelo["no_terminales"] else []), modelo)["aceptado"])
        with self.assertRaisesRegex(ValueError, "Conflicto"):
            generar_slr({"inicial": "S", "producciones": [["S", ["S", "S"]], ["S", ["a"]]]})


class TraduccionTests(unittest.TestCase):
    def test_codigo_ejemplo_exacto(self):
        r = c.compilar(c.EJEMPLO)
        texto = "\n".join(x["op"]+(" "+str(x["arg"]) if "arg" in x else "") for x in r["codigo"])
        self.assertEqual(texto, "PUSH 28\nSTORE S01\nPUSH 15\nSTORE S02\nLOAD S01\nPUSH 26\nGT\nJUMP_IF_FALSE L1\nLOAD S02\nPUSH 20\nLT\nJUMP_IF_FALSE L1\nEMIT A01\nLABEL L1")
        self.assertEqual(r["salida"], {"estado": "aceptado", "avisos": [{"codigo": "A01", "descripcion": c.ACCIONES["A01"]}]})

    def test_falso_valido_y_cortocircuito(self):
        r = c.compilar(c.EJEMPLO.replace("28", "20").replace("15", "80"))
        self.assertTrue(r["aceptado"])
        self.assertEqual(r["salida"]["avisos"], [])
        self.assertNotIn(8, r["simulacion"]["ejecutadas"])

    def test_simulador_independiente_y_reglas_en_orden(self):
        r = c.compilar(programa()+" SI S01<30 ENTONCES AVISAR A02;")
        self.assertEqual([x["codigo"] for x in r["salida"]["avisos"]], ["A01", "A02"])
        codigo = copy.deepcopy(r["codigo"])
        codigo[0]["arg"] = 20
        self.assertEqual([x["codigo"] for x in ejecutar(codigo)["avisos"]], ["A02"])
        self.assertEqual(r["registros"][0]["estructura"]["cargas"][0]["valor"], "28")

    def test_comparadores(self):
        for op, umbral, esperado in [(">", 26, True), ("<", 26, False), (">=", 28, True),
                                     ("<=", 28, True), ("==", 28, True), ("!=", 28, False)]:
            r = c.compilar(programa(comparador=op, umbral=umbral))
            self.assertTrue(r["aceptado"])
            self.assertEqual(bool(r["salida"]["avisos"]), esperado)

    def test_vm_rechaza_codigo_invalido(self):
        for codigo in [[], [{"op": "EXEC", "arg": "x"}], [{"op": "GT"}], [{"op": "LOAD", "arg": "S01"}],
                       [{"op": "PUSH", "arg": 1}], [{"op": "JUMP_IF_FALSE", "arg": "L99"}],
                       [{"op": "LABEL", "arg": "L1"}, {"op": "JUMP_IF_FALSE", "arg": "L1"}]]:
            with self.assertRaises(ValueError):
                ejecutar(codigo)


class AutomatasTests(unittest.TestCase):
    def test_ejemplos_y_alfabetos(self):
        for token, patron in a.EXPRESIONES.items():
            directo = a.crear_directo(token)
            self.assertFalse(any(t["simbolo"] == "ε" for t in directo["transiciones"]))
            for i, grupo in enumerate(a.EJEMPLOS[token]):
                for texto in grupo:
                    self.assertEqual(acepta(directo, texto), i == 0, (token, texto))

    def test_equivalencia_exacta_directo_thompson_y_minimo(self):
        for token, patron in a.EXPRESIONES.items():
            modelos = [a.convertir_afd(a.crear_directo(token)), a.convertir_afd(a.crear_afnd(patron))]
            modelos.append(a.minimizar_afd(modelos[0]))
            for otro in modelos[1:]:
                izquierdo = modelos[0]
                deltas = [{(t["origen"], t["simbolo"]): t["destino"] for t in m["transiciones"]} for m in [izquierdo, otro]]
                cola, vistos = deque([(izquierdo["inicial"], otro["inicial"])]), set()
                while cola:
                    x, y = cola.popleft()
                    if (x, y) in vistos:
                        continue
                    vistos.add((x, y))
                    self.assertEqual(x in izquierdo["finales"], y in otro["finales"])
                    cola.extend((deltas[0].get((x, s)), deltas[1].get((y, s))) for s in set(a.obtener_alfabeto(izquierdo)) | set(a.obtener_alfabeto(otro)))

    def test_minimos_distinguibles(self):
        for token in a.EXPRESIONES:
            modelo = a.minimizar_afd(a.convertir_afd(a.crear_directo(token)))
            delta = {(t["origen"], t["simbolo"]): t["destino"] for t in modelo["transiciones"]}
            for x, y in itertools.combinations(modelo["estados"], 2):
                cola, vistos, distinguible = deque([(x, y)]), set(), False
                while cola:
                    p, q = cola.popleft()
                    if (p, q) in vistos:
                        continue
                    vistos.add((p, q))
                    if (p in modelo["finales"]) != (q in modelo["finales"]):
                        distinguible = True
                        break
                    cola.extend((delta[p, s], delta[q, s]) for s in a.obtener_alfabeto(modelo))
                self.assertTrue(distinguible)

    def test_thompson_general_y_errores(self):
        for patron, cadena in [("", ""), ("a*", "aaa"), ("(a|b)*abb", "aabb"), ("a?b{1,3}", "bbb")]:
            afnd = a.crear_afnd(patron)
            self.assertTrue(acepta(afnd, cadena))
            self.assertEqual(acepta(a.minimizar_afd(a.convertir_afd(afnd)), cadena), True)
        for patron in ["[z-a]", "(", "a{3,2}"]:
            with self.assertRaises(ValueError):
                a.crear_afnd(patron)
