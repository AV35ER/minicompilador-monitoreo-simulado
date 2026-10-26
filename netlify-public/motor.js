/* Thompson, subconjuntos y particiones. El build aporta las reglas desde Python. */
(function (global) {
    "use strict";
    const ordenar = valores => [...new Set(valores)].sort();
    const escapar = valor => String(valor).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

    function expandir(simbolo) {
        if (simbolo === "ε") return [];
        if (!simbolo.startsWith("[") || !simbolo.endsWith("]")) return [simbolo];
        const contenido = simbolo.slice(1, -1), caracteres = [];
        for (let i = 0; i < contenido.length; i++) {
            if (i + 2 < contenido.length && contenido[i + 1] === "-") {
                const inicio = contenido.codePointAt(i), fin = contenido.codePointAt(i + 2);
                if (inicio > fin) throw new Error("Rango invertido");
                for (let n = inicio; n <= fin; n++) caracteres.push(String.fromCodePoint(n));
                i += 2;
            } else caracteres.push(contenido[i]);
        }
        return ordenar(caracteres);
    }

    function analizarRegex(texto) {
        let pos = 0;
        const ver = () => texto[pos] || "";
        function alternativa() {
            const nodos = [concatenacion()];
            while (ver() === "|") {pos++; nodos.push(concatenacion());}
            return nodos.length > 1 ? ["alternativa", nodos] : nodos[0];
        }
        function concatenacion() {
            const nodos = [];
            while (ver() && !"|)".includes(ver())) nodos.push(repeticion());
            return ["concatenacion", nodos];
        }
        function repeticion() {
            const nodo = atomo(), signo = ver();
            if (signo && "*+?".includes(signo)) {
                pos++;
                return ["repeticion", nodo, ...({"*": [0, null], "+": [1, null], "?": [0, 1]}[signo])];
            }
            if (signo !== "{") return nodo;
            const fin = texto.indexOf("}", pos), contenido = texto.slice(pos + 1, fin);
            if (fin < 0 || !/^[0-9]+(?:,[0-9]*)?$/.test(contenido)) throw new Error("Repetición inválida");
            const partes = contenido.split(","), minimo = Number(partes[0]);
            const maximo = partes.length === 1 ? minimo : partes[1] === "" ? null : Number(partes[1]);
            if (maximo !== null && maximo < minimo) throw new Error("Límites invertidos");
            pos = fin + 1;
            return ["repeticion", nodo, minimo, maximo];
        }
        function atomo() {
            let signo = ver(); pos++;
            if (signo === "(") {
                const nodo = alternativa();
                if (ver() !== ")") throw new Error("Grupo sin cierre");
                pos++; return nodo;
            }
            if (signo === "[") {
                const fin = texto.indexOf("]", pos), valor = texto.slice(pos - 1, fin + 1);
                if (fin < 0 || valor.startsWith("[^") || valor.includes("\\") || !expandir(valor).length) throw new Error("Clase inválida");
                pos = fin + 1; return ["simbolo", valor];
            }
            if (signo === "\\") {
                signo = ver(); pos++;
                if (!signo || /[\p{L}\p{N}]/u.test(signo)) throw new Error("Escape no soportado");
            } else if ("*+?{}].^ε".includes(signo)) throw new Error("Operador no soportado o sin operando");
            return ["simbolo", signo];
        }
        const nodo = alternativa();
        if (pos !== texto.length) throw new Error("Símbolo inesperado en posición " + pos);
        return nodo;
    }

    function crearAFND(expresion) {
        const estados = [], transiciones = [];
        const nuevo = () => {const e = "q" + estados.length; estados.push(e); return e;};
        const conectar = (origen, simbolo, destino) => transiciones.push({origen, simbolo, destino});
        function simbolo(valor) {const a = nuevo(), b = nuevo(); conectar(a, valor, b); return [a, b];}
        function unir(partes) {
            if (!partes.length) return simbolo("ε");
            for (let i = 1; i < partes.length; i++) conectar(partes[i - 1][1], "ε", partes[i][0]);
            return [partes[0][0], partes.at(-1)[1]];
        }
        function construir(nodo) {
            const [tipo, hijo, minimo, maximo] = nodo;
            if (tipo === "simbolo") return simbolo(hijo);
            if (tipo === "concatenacion") return unir(hijo.map(construir));
            if (tipo === "alternativa") {
                const inicio = nuevo(), fin = nuevo();
                for (const rama of hijo) {const [a, b] = construir(rama); conectar(inicio, "ε", a); conectar(b, "ε", fin);}
                return [inicio, fin];
            }
            if (minimo === 1 && maximo === null) {
                const [a, b] = construir(hijo), inicio = nuevo(), fin = nuevo();
                conectar(inicio, "ε", a); conectar(b, "ε", a); conectar(b, "ε", fin);
                return [inicio, fin];
            }
            const partes = Array.from({length: minimo}, () => construir(hijo));
            const cantidad = maximo === null ? 1 : maximo - minimo;
            for (let i = 0; i < cantidad; i++) {
                const [a, b] = construir(hijo), inicio = nuevo(), fin = nuevo();
                conectar(inicio, "ε", a); conectar(inicio, "ε", fin);
                if (maximo === null) conectar(b, "ε", a);
                conectar(b, "ε", fin); partes.push([inicio, fin]);
            }
            return unir(partes);
        }
        const [inicial, fin] = construir(analizarRegex(expresion));
        return {estados, inicial, finales: [fin], transiciones};
    }

    const alfabeto = automata => ordenar(automata.transiciones.flatMap(t => expandir(t.simbolo)));
    function cierre(estados, transiciones) {
        const conjunto = new Set(estados), pendientes = [...conjunto];
        while (pendientes.length) {
            const actual = pendientes.pop();
            for (const t of transiciones) if (t.origen === actual && t.simbolo === "ε" && !conjunto.has(t.destino)) {
                conjunto.add(t.destino); pendientes.push(t.destino);
            }
        }
        return [...conjunto].sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
    }
    function convertirAFD(afnd) {
        const simbolos = alfabeto(afnd), conjuntos = [cierre([afnd.inicial], afnd.transiciones)];
        const nombres = new Map([[JSON.stringify(conjuntos[0]), "D0"]]);
        const afd = {estados: ["D0"], inicial: "D0", finales: [], transiciones: [], equivalencias: {}};
        for (let i = 0; i < conjuntos.length; i++) {
            const conjunto = conjuntos[i], origen = "D" + i;
            afd.equivalencias[origen] = conjunto;
            if (conjunto.some(e => afnd.finales.includes(e))) afd.finales.push(origen);
            for (const simbolo of simbolos) {
                const destinos = afnd.transiciones.filter(t => conjunto.includes(t.origen) && expandir(t.simbolo).includes(simbolo)).map(t => t.destino);
                const siguiente = cierre(destinos, afnd.transiciones), clave = JSON.stringify(siguiente);
                if (!nombres.has(clave)) {
                    const nombre = "D" + conjuntos.length;
                    nombres.set(clave, nombre); conjuntos.push(siguiente); afd.estados.push(nombre);
                }
                afd.transiciones.push({origen, simbolo, destino: nombres.get(clave)});
            }
        }
        return afd;
    }
    function minimizarAFD(afd) {
        const simbolos = alfabeto(afd), delta = new Map(afd.transiciones.map(t => [t.origen + ":" + t.simbolo, t.destino]));
        let bloques = [afd.estados.filter(e => !afd.finales.includes(e)), afd.estados.filter(e => afd.finales.includes(e))].filter(g => g.length);
        while (true) {
            const pertenencia = new Map(bloques.flatMap((g, i) => g.map(e => [e, i]))), nuevos = [];
            for (const grupo of bloques) {
                const firmas = new Map();
                for (const estado of grupo) {
                    const firma = JSON.stringify(simbolos.map(s => pertenencia.get(delta.get(estado + ":" + s))));
                    if (!firmas.has(firma)) firmas.set(firma, []);
                    firmas.get(firma).push(estado);
                }
                nuevos.push(...firmas.values());
            }
            if (nuevos.length === bloques.length) break;
            bloques = nuevos;
        }
        bloques.sort((a, b) => Math.min(...a.map(e => afd.estados.indexOf(e))) - Math.min(...b.map(e => afd.estados.indexOf(e))));
        const nombres = new Map(bloques.flatMap((g, i) => g.map(e => [e, "M" + i])));
        return {
            estados: bloques.map((_, i) => "M" + i), inicial: nombres.get(afd.inicial),
            finales: bloques.flatMap((g, i) => afd.finales.includes(g[0]) ? ["M" + i] : []),
            transiciones: bloques.flatMap((g, i) => simbolos.map(simbolo => ({origen: "M" + i, simbolo, destino: nombres.get(delta.get(g[0] + ":" + simbolo))}))),
            equivalencias: Object.fromEntries(bloques.map((g, i) => ["M" + i, g]))
        };
    }
    function quintupla(a) {return {Q: a.estados, Sigma: alfabeto(a), delta: a.transiciones, q0: a.inicial, F: a.finales};}
    function tabla(a) {
        const simbolos = alfabeto(a);
        if (a.transiciones.some(t => t.simbolo === "ε")) simbolos.push("ε");
        return a.estados.map(estado => Object.fromEntries([["estado", estado], ...simbolos.map(s => [s,
            ordenar(a.transiciones.filter(t => t.origen === estado && (s === t.simbolo || expandir(t.simbolo).includes(s))).map(t => t.destino))])]));
    }
    function etiqueta(simbolos) {
        const caracteres = ordenar(simbolos), partes = [];
        if (caracteres.some(c => [...c].length !== 1)) return caracteres.map(c => c === " " ? "␠" : c).join(", ");
        for (let i = 0; i < caracteres.length;) {
            let j = i;
            while (j + 1 < caracteres.length && /[\p{L}\p{N}]/u.test(caracteres[j]) && /[\p{L}\p{N}]/u.test(caracteres[j + 1]) && caracteres[j + 1].codePointAt(0) === caracteres[j].codePointAt(0) + 1) j++;
            if (j - i >= 2) partes.push("[" + caracteres[i] + "-" + caracteres[j] + "]");
            else partes.push(...caracteres.slice(i, j + 1).map(c => c === " " ? "␠" : c));
            i = j + 1;
        }
        return partes.join(", ");
    }
    function tablaVisual(a, esAFND, filas = tabla(a)) {
        const grupos = new Map();
        for (const s of [...alfabeto(a), ...(esAFND && a.transiciones.some(t => t.simbolo === "ε") ? ["ε"] : [])]) {
            const firma = JSON.stringify([s === "ε", filas.map(f => f[s] || [])]);
            if (!grupos.has(firma)) grupos.set(firma, []);
            grupos.get(firma).push(s);
        }
        const columnas = [...grupos.values()].map(g => [etiqueta(g), g]);
        return {alfabeto: columnas.map(g => g[0]), grupos: columnas, filas: filas.map(f => ({estado: f.estado,
            inicial: f.estado === a.inicial, final: a.finales.includes(f.estado),
            destinos: Object.fromEntries(columnas.map(([nombre, simbolos]) => [nombre, (f[simbolos[0]] || []).join(", ") || "∅"]))}))};
    }

    function crearDirecto(definicion) {
        const [cantidad, finales, aristas] = definicion;
        return {estados: Array.from({length: cantidad}, (_, i) => "q" + i), inicial: "q0",
            finales: finales.map(i => "q" + i),
            transiciones: aristas.map(([a, simbolo, b]) => ({origen: "q" + a, simbolo, destino: "q" + b}))};
    }
    function sinSumidero(a, muertos) {
        return {...a, estados: a.estados.filter(e => !muertos.has(e)), finales: a.finales.filter(e => !muertos.has(e)),
            transiciones: a.transiciones.filter(t => !muertos.has(t.origen) && !muertos.has(t.destino)),
            equivalencias: Object.fromEntries(Object.entries(a.equivalencias).filter(([e]) => !muertos.has(e)))};
    }

    function generarTodos(config) {
        const nombres = config.orden_tokens || Object.keys(config.expresiones);
        return Object.fromEntries(nombres.map(nombre => {
            const expresion = config.expresiones[nombre];
            const definicion = config.construcciones_directas?.[nombre];
            const afnd = definicion ? crearDirecto(definicion) : crearAFND(expresion);
            let afd = convertirAFD(afnd), afd_minimo = minimizarAFD(afd);
            if (definicion) {
                const muertos = new Set(Object.entries(afd.equivalencias).filter(([, g]) => !g.length).map(([e]) => e));
                const muertosMinimos = new Set(Object.entries(afd_minimo.equivalencias).filter(([, g]) => g.every(e => muertos.has(e))).map(([e]) => e));
                afd = sinSumidero(afd, muertos);
                afd_minimo = sinSumidero(afd_minimo, muertosMinimos);
            }
            const datos = {expresion, ejemplos: config.ejemplos[nombre], afnd, afd, afd_minimo};
            for (const tipo of ["afnd", "afd", "afd_minimo"]) {
                datos["quintupla_" + tipo] = quintupla(datos[tipo]);
                datos["tabla_" + tipo] = tabla(datos[tipo]);
                datos["tabla_visual_" + tipo] = tablaVisual(datos[tipo], tipo === "afnd", datos["tabla_" + tipo]);
            }
            return [nombre, datos];
        }));
    }
    const motor = {crearDirecto, expandir, analizarRegex, crearAFND, alfabeto, cierre, convertirAFD, minimizarAFD, quintupla, tabla, etiqueta, tablaVisual, generarTodos, escapar};
    if (typeof module !== "undefined" && module.exports) module.exports = motor;
    else global.MotorAutomatas = motor;
})(globalThis);
