(function(global) {
"use strict";
const ordenar = valores => [...new Set(valores)].sort();
    function generarSLR(gramatica) {
        const inicial = gramatica.inicial;
        const simbolos = new Set(gramatica.producciones.flatMap(([izq, der]) => [izq, ...der]));
        let aumentado = inicial + "'";
        while (simbolos.has(aumentado)) aumentado += "'";
        const producciones = [[aumentado, [inicial]], ...gramatica.producciones];
        const noTerminales = [...new Set(producciones.map(p => p[0]))];
        const terminales = [...new Set(producciones.flatMap(p => p[1]).filter(s => !noTerminales.includes(s)))];
        const primeros = Object.fromEntries([...terminales.map(s => [s, new Set([s])]), ...noTerminales.map(s => [s, new Set()])]);
        function primero(secuencia) {
            const resultado = new Set();
            for (const s of secuencia) {
                for (const c of primeros[s]) if (c !== "ε") resultado.add(c);
                if (!primeros[s].has("ε")) return resultado;
            }
            resultado.add("ε"); return resultado;
        }
        function agregar(conjunto, valores) {
            let cambio = false;
            for (const v of valores) if (!conjunto.has(v)) {conjunto.add(v); cambio = true;}
            return cambio;
        }
        let cambio = true;
        while (cambio) {
            cambio = false;
            for (const [izquierda, derecha] of producciones) cambio = agregar(primeros[izquierda], primero(derecha)) || cambio;
        }
        const siguientes = Object.fromEntries(noTerminales.map(s => [s, new Set()]));
        siguientes[aumentado].add("$"); cambio = true;
        while (cambio) {
            cambio = false;
            for (const [izquierda, derecha] of producciones) derecha.forEach((s, i) => {
                if (!siguientes[s]) return;
                const sufijo = primero(derecha.slice(i + 1));
                const nuevos = [...sufijo].filter(c => c !== "ε");
                if (sufijo.has("ε")) nuevos.push(...siguientes[izquierda]);
                cambio = agregar(siguientes[s], nuevos) || cambio;
            });
        }
        function cierre(items) {
            const resultado = new Map(items.map(item => [JSON.stringify(item), item]));
            let cambio = true;
            while (cambio) {
                cambio = false;
                for (const [p, punto] of [...resultado.values()]) {
                    const s = producciones[p][1][punto];
                    producciones.forEach(([izquierda], j) => {
                        const clave = JSON.stringify([j, 0]);
                        if (izquierda === s && !resultado.has(clave)) {resultado.set(clave, [j, 0]); cambio = true;}
                    });
                }
            }
            return [...resultado.values()].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
        }
        const estados = [cierre([[0, 0]])], nombres = new Map([[JSON.stringify(estados[0]), 0]]), transiciones = [];
        for (let origen = 0; origen < estados.length; origen++) {
            for (const simbolo of [...terminales, ...noTerminales.slice(1)]) {
                const items = estados[origen].filter(([p, d]) => producciones[p][1][d] === simbolo).map(([p, d]) => [p, d + 1]);
                if (!items.length) continue;
                const destino = cierre(items), clave = JSON.stringify(destino);
                if (!nombres.has(clave)) {nombres.set(clave, estados.length); estados.push(destino);}
                transiciones.push({origen, simbolo, destino: nombres.get(clave)});
            }
        }
        const acciones = estados.map(() => ({})), saltos = estados.map(() => ({}));
        function accion(estado, simbolo, valor) {
            const anterior = acciones[estado][simbolo];
            if (anterior !== undefined && anterior !== valor) throw new Error(`Conflicto SLR en I${estado}, ${simbolo}: ${anterior} / ${valor}`);
            acciones[estado][simbolo] = valor;
        }
        for (const t of transiciones) {
            if (terminales.includes(t.simbolo)) accion(t.origen, t.simbolo, "d" + t.destino);
            else saltos[t.origen][t.simbolo] = t.destino;
        }
        estados.forEach((estado, i) => {
            for (const [p, punto] of estado) if (punto === producciones[p][1].length) {
                for (const s of p === 0 ? ["$"] : ordenar(siguientes[producciones[p][0]])) accion(i, s, p === 0 ? "aceptar" : "r" + p);
            }
        });
        return {inicial, producciones, terminales, no_terminales: noTerminales.slice(1), estados, transiciones,
            primeros: Object.fromEntries(noTerminales.slice(1).map(s => [s, ordenar(primeros[s])])),
            siguientes: Object.fromEntries(noTerminales.slice(1).map(s => [s, ordenar(siguientes[s])])), acciones, saltos, conflictos: []};
    }
    function derivar(arbol) {
        const frontera = [arbol], pasos = [[arbol.simbolo]];
        while (frontera.some(n => n.lexema === undefined)) {
            const i = frontera.findIndex(n => n.lexema === undefined);
            frontera.splice(i, 1, ...frontera[i].hijos); pasos.push(frontera.map(n => n.simbolo));
        }
        return pasos;
    }
    function analizarSintaxis(tokens, modelo, reducir) {
        const pila = [0], nodos = [], valores = [], traza = []; let pos = 0;
        while (true) {
            const simbolo = tokens[pos]?.token || "$", accion = modelo.acciones[pila.at(-1)][simbolo];
            traza.push({pila: [...pila], entrada: [...tokens.slice(pos).map(t => t.token), "$"], accion: accion || "error"});
            if (!accion) {
                const esperados = Object.keys(modelo.acciones[pila.at(-1)]).sort();
                const columna = tokens[pos]?.columna ?? (tokens.length ? tokens.at(-1).columna + [...tokens.at(-1).lexema].length : 1);
                return {aceptado: false, arbol: null, derivacion: [], traza, errores_sintacticos: [{linea: tokens[pos]?.linea ?? tokens.at(-1)?.linea ?? 1, columna, lexema: tokens[pos]?.lexema ?? "$", detalle: "Se esperaba " + esperados.join(", ") + "; se recibió " + simbolo + ".", esperados}]};
            }
            if (accion === "aceptar") return {aceptado: true, arbol: nodos[0], derivacion: derivar(nodos[0]), traza, errores_sintacticos: [], estructura: reducir ? valores[0] : null};
            const numero = Number(accion.slice(1));
            if (accion[0] === "d") {nodos.push({simbolo, lexema: tokens[pos].lexema, hijos: []}); valores.push(tokens[pos]); pila.push(numero); pos++;}
            else {
                const [izquierda, derecha] = modelo.producciones[numero], hijos = derecha.length ? nodos.splice(-derecha.length) : [];
                const argumentos = derecha.length ? valores.splice(-derecha.length) : [];
                valores.push(reducir ? reducir(izquierda, argumentos) : null);
                if (derecha.length) pila.splice(-derecha.length);
                nodos.push({simbolo: izquierda, hijos}); pila.push(modelo.saltos[pila.at(-1)][izquierda]);
            }
        }
    }

const slr = {generarSLR, analizarSintaxis};
if (typeof module !== "undefined" && module.exports) module.exports = slr; else global.SLR = slr;
})(globalThis);