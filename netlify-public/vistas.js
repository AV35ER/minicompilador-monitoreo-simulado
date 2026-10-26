(function (global) {
    "use strict";
    const motor = typeof module !== "undefined" && module.exports ? require("./motor.js") : global.MotorAutomatas;
    const e = motor.escapar;
    const tipos = {afnd: "AFND", afd: "AFD", afd_minimo: "AFD mínimo parcial"};
    const celdas = (valores, etiqueta = "td") => valores.map(v => `<${etiqueta}>${e(v)}</${etiqueta}>`).join("");
    const tablaHTML = (cabecera, filas, clase = "") => `<div class="tabla-contenedor"><table class="${clase}"><thead><tr>${celdas(cabecera, "th")}</tr></thead><tbody>${filas.map(f => `<tr>${celdas(f)}</tr>`).join("")}</tbody></table></div>`;

    function dibujar(a, id) {
        // Capas por distancia desde el inicio; se conservan todas las aristas.
        const niveles = new Map([[a.inicial, 0]]), pendientes = [a.inicial];
        for (let i = 0; i < pendientes.length; i++) {
            for (const t of a.transiciones) if (t.origen === pendientes[i] && !niveles.has(t.destino)) {
                niveles.set(t.destino, niveles.get(t.origen) + 1); pendientes.push(t.destino);
            }
        }
        const capas = new Map();
        for (const estado of a.estados) {
            const nivel = niveles.get(estado) || 0;
            if (!capas.has(nivel)) capas.set(nivel, []);
            capas.get(nivel).push(estado);
        }
        const alto = Math.max(260, Math.max(...[...capas.values()].map(g => g.length)) * 150 + 120);
        const ancho = Math.max(360, capas.size * 190 + 80), puntos = new Map();
        for (const [nivel, grupo] of capas) grupo.forEach((estado, i) => puntos.set(estado, [80 + nivel * 190, (i + 1) * alto / (grupo.length + 1)]));
        const grupos = new Map();
        for (const t of a.transiciones) {
            const clave = JSON.stringify([t.origen, t.destino]);
            if (!grupos.has(clave)) grupos.set(clave, []);
            grupos.get(clave).push(t.simbolo);
        }
        let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${ancho} ${alto}" width="${ancho}" height="${alto}" role="img" aria-label="Autómata ${e(id)}"><defs><marker id="flecha-${e(id)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#444"/></marker></defs>`;
        const flecha = `fill="none" stroke="#444" stroke-width="1.2" marker-end="url(#flecha-${e(id)})"`;
        const [ix, iy] = puntos.get(a.inicial);
        svg += `<path d="M${ix - 60} ${iy} H${ix - 25}" ${flecha}/>`;
        for (const [clave, simbolos] of grupos) {
            const [origen, destino] = JSON.parse(clave), [x1, y1] = puntos.get(origen), [x2, y2] = puntos.get(destino);
            let camino, tx, ty;
            if (origen === destino) {
                camino = `M${x1 - 15} ${y1 - 20} C${x1 - 80} ${y1 - 100} ${x1 + 80} ${y1 - 100} ${x1 + 15} ${y1 - 20}`;
                tx = x1; ty = y1 - 80;
            } else {
                const dx = x2 - x1, dy = y2 - y1, distancia = Math.hypot(dx, dy);
                const curva = 30 + Math.min(45, Math.abs(dx) / 10);
                const cx = (x1 + x2) / 2 - dy / distancia * curva, cy = (y1 + y2) / 2 + dx / distancia * curva;
                const d1 = Math.hypot(cx - x1, cy - y1), d2 = Math.hypot(cx - x2, cy - y2);
                camino = `M${x1 + (cx - x1) / d1 * 25} ${y1 + (cy - y1) / d1 * 25} Q${cx} ${cy} ${x2 + (cx - x2) / d2 * 25} ${y2 + (cy - y2) / d2 * 25}`;
                tx = (x1 + 2 * cx + x2) / 4; ty = (y1 + 2 * cy + y2) / 4 - 8;
            }
            const etiqueta = motor.etiqueta(simbolos);
            svg += `<g class="arista" data-origen="${e(origen)}" data-destino="${e(destino)}" data-simbolos="${e(JSON.stringify(simbolos))}"><title>${e(origen)} → ${e(destino)}: ${e(etiqueta)}</title><path d="${camino}" ${flecha}/><text x="${tx}" y="${ty}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" stroke="white" stroke-width="4" paint-order="stroke" fill="#222">${e(etiqueta)}</text></g>`;
        }
        for (const estado of a.estados) {
            const [x, y] = puntos.get(estado), final = a.finales.includes(estado);
            svg += `<g class="estado" data-estado="${e(estado)}" data-inicial="${estado === a.inicial}" data-final="${final}"><circle cx="${x}" cy="${y}" r="24" fill="white" stroke="#333"/>${final ? `<circle cx="${x}" cy="${y}" r="20" fill="none" stroke="#333"/>` : ""}<text x="${x}" y="${y + 5}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14">${e(estado)}</text></g>`;
        }
        return svg + "</svg>";
    }

    function panelAutomata(nombre, tipo, datos) {
        const a = datos[tipo], q = datos["quintupla_" + tipo], tabla = datos["tabla_visual_" + tipo];
        const id = "grafico-" + nombre + "-" + tipo;
        let html = `<div class="panel panel-automata" data-tipo="${tipo}" ><h3>${tipos[tipo]} — ${e(nombre)}</h3><p>M = (Q, Σ, δ, q₀, F)</p>${tipo === "afnd" ? "" : '<p class="nota">AFD parcial: δ: Q × Σ ⇀ Q. Las transiciones no definidas rechazan; se omite el sumidero implícito.</p>'}<div class="controles"><button type="button" onclick="cambiarZoom('${id}', 1.25)">Acercar +</button><button type="button" onclick="cambiarZoom('${id}', 0.8)">Alejar −</button><button type="button" onclick="reiniciarZoom('${id}')">Restablecer</button></div><div class="grafico" id="${id}" tabindex="0" role="region" aria-label="Gráfico ${tipos[tipo]} de ${e(nombre)}; desplazamiento y zoom disponibles">${dibujar(a, id)}</div><h3>Quíntupla</h3><div class="quintupla"><strong>Q</strong><div>${e(q.Q.join(", "))}</div><strong>Σ</strong><div>${e(motor.etiqueta(q.Sigma))}</div><strong>δ</strong><div>Ver tabla de transiciones.</div><strong>q₀</strong><div>${e(q.q0)}</div><strong>F</strong><div>${e(q.F.join(", "))}</div></div>`;
        if (tipo !== "afnd") {
            html += `<details><summary>Correspondencia de estados</summary><h3>${tipo === "afd" ? "Estados equivalentes del AFND" : "Estados del AFD agrupados"}</h3>`;
            html += tablaHTML([tipos[tipo], tipo === "afd" ? "Conjunto de estados AFND" : "Estados AFD originales"], Object.entries(a.equivalencias).map(([estado, conjunto]) => [estado, conjunto.join(", ") || "∅ (sumidero)"]));
            html += "</details>";
        }
        html += `<h3>Tabla de transiciones</h3><div class="transiciones">${tablaHTML(["Estado", ...tabla.alfabeto], tabla.filas.map(f => [(f.inicial ? "→" : "") + (f.final ? "*" : "") + f.estado, ...tabla.alfabeto.map(s => f.destinos[s])]))}</div><p class="nota">→ Inicial. * Aceptación. ∅ Sin transición. ␠ Espacio. Los símbolos agrupados comparten destinos. Una transición inexistente rechaza la cadena; se omite el sumidero implícito.</p></div>`;
        return html;
    }
    function renderizarSalida(r) {
        let html=`<section><h2>B. Representación de salida</h2><p class="${r.aceptado?"correcto":"error"}">${r.aceptado?"Programa aceptado.":"Programa rechazado. No se traduce ni ejecuta parcialmente."}</p>`;
        const mostrar=(error,fase)=>`<p class="error">Error ${fase}, línea ${error.linea}, columna ${error.columna}: ${error.lexema===undefined?"":e(error.lexema)+". "}${e(error.detalle)}</p>`;
        html+=r.errores.map(error=>mostrar(error,"léxico")).join("");
        for(const registro of r.registros){html+=registro.errores_sintacticos.map(error=>mostrar(error,"sintáctico")).join("");html+=registro.errores_semanticos.map(error=>mostrar(error,"semántico")).join("");}
        if(r.aceptado) {
            html+=`<h3>Resultado de la simulación</h3><p>${r.simulacion.avisos.length} ${r.simulacion.avisos.length === 1 ? "aviso" : "avisos"}; ${r.simulacion.pasos} instrucciones intermedias ejecutadas.</p>`;
            html+=r.simulacion.avisos.length?r.simulacion.avisos.map(a=>`<p>${e(a.codigo)}: ${e(a.descripcion)}</p>`).join(""):"<p>Las condiciones no generan avisos. El programa sigue siendo válido.</p>";
            html+=`<p>El simulador ejecuta el código intermedio. El JSON contiene los avisos obtenidos.</p><pre id="salida-json">${e(JSON.stringify(r.salida,null,2))}</pre><details><summary>Ver código intermedio (${r.codigo.length} instrucciones)</summary><pre id="codigo-intermedio">${e(r.codigo.map(c=>c.op+(c.arg===undefined?"":" "+c.arg)).join("\n"))}</pre></details>`;
        } else html+="<p>Sin código intermedio, simulación ni JSON de éxito.</p>";
        return html+'<button type="button" onclick="window.print()">Imprimir informe / guardar PDF</button></section>';
    }
    function renderizarSemantica(resultado) {
        let html='<section id="analisis-semantico"><h3>C.3 Análisis semántico</h3><p>Comprueba códigos, rangos enteros, cargas únicas y referencias previas. Una condición falsa no es un error.</p>';
        for(const r of resultado.registros) {
            if(r.atributos.length) {
                html+=`<p>${r.atributos.filter(a=>a.valido).length} de ${r.atributos.length} comprobaciones válidas; ${Object.keys(resultado.simulacion?.memoria || {}).length} símbolos cargados. Resultado: ${r.errores_semanticos.length ? "rechazado" : "válido"}.</p>`;

                html+='<h4>Símbolos del programa</h4>'+tablaHTML(["Sensor","Valor fuente","Valor simulado"],r.estructura.cargas.map(c=>[c.sensor,c.valor,resultado.simulacion?.memoria[c.sensor]??"No ejecutado"]));
                html+='<details><summary>Ver comprobaciones semánticas</summary>';
                html+=tablaHTML(["Línea","Campo","Lexema","Tipo","Acción realizada","Resultado"],r.atributos.map(a=>[a.linea,a.campo,a.lexema,a.tipo,a.accion,a.valido?"Válido":"Inválido"]));
                html+="</details>";
            } else html+=`<p>No ejecutado: el programa tiene errores de análisis ${e(r.fase)}.</p>`;
            html+=r.errores_semanticos.map(error=>`<p class="error">Línea ${error.linea}, columna ${error.columna}: ${e(error.detalle)}</p>`).join("");
        }
        if(resultado.correspondencias.length)html+='<h4>Correspondencia entre reglas y traducción</h4>'+tablaHTML(["Regla","Línea","Índices del código (desde 0)","Etiqueta de salida"],resultado.correspondencias.map(c=>[c.regla,c.linea,c.inicio+"–"+c.fin,c.etiqueta]));
        return html+"</section>";
    }
    function renderizarSintaxis(resultado) {
        const slr = resultado.slr;
        function arbol(n, nivel = 0) {
            if (n.hijos.length) {
                const compacto = ["CARGA", "COMP"].includes(n.simbolo);
                const resumen = compacto
                    ? ` — <code>${e(n.hijos.map(h => h.lexema).join(" ").replace(" ;", ";"))}</code>`
                    : ` → ${e(n.hijos.map(h => h.simbolo === "PUNTO_Y_COMA" ? "PYC" : h.simbolo).join(" "))}`;
                return `<details class="nodo-sintactico" data-simbolo="${e(n.simbolo)}"${nivel < 3 && !compacto ? " open" : ""}><summary>${e(n.simbolo)}${resumen}</summary><div class="hijos-sintacticos">${n.hijos.map(h => arbol(h, nivel + 1)).join("")}</div></details>`;
            }
            return `<span class="hoja-sintactica" data-simbolo="${e(n.simbolo)}"${n.lexema === undefined ? "" : ` data-lexema="${e(n.lexema)}"`}><strong>${e(n.simbolo)}</strong>: ${n.lexema === undefined ? "ε" : e(n.lexema)}</span>`;
        }
        let html = `<section id="analisis-sintactico"><h3>C.2 Análisis sintáctico</h3><p>${slr.estados.length} estados LR(0); ${slr.conflictos.length} conflictos.</p>`;
        for (const r of resultado.registros) {
            html += `<h4>Programa: ${r.sintaxis_aceptada ? "SLR(1) válido" : r.fase === "léxico" ? "no ejecutado por errores léxicos" : "estructura rechazada"}</h4>`;
            html += r.errores_sintacticos.map(error => `<p class="error">Línea ${error.linea}, columna ${error.columna}: ${e(error.detalle)}</p>`).join("");
            if (r.arbol) html += `<div class="arbol-oculto" hidden><h3>Árbol sintáctico</h3><div class="arbol">${arbol(r.arbol)}</div><p class="nota">Abre o cierra cada nodo con su encabezado. Las hojas muestran los lexemas del programa ingresado. La aceptación sintáctica precede a las validaciones de códigos, rangos y referencias.</p></div>`;

        }
        const [aumentado, derecha] = slr.producciones[0];
        html += `<div id="gramatica" hidden><h4>Gramática y tabla SLR(1)</h4><p>BNF: PYC abrevia PUNTO_Y_COMA. ε representa la producción vacía.</p><div class="bnf">${slr.no_terminales.map(n => `<div><code>${e(n)} → ${slr.producciones.slice(1).filter(([izq]) => izq === n).map(([,der]) => e(der.join(" ").replaceAll("PUNTO_Y_COMA", "PYC") || "ε")).join(" | ")}</code></div>`).join("")}</div><details><summary>Detalles técnicos del análisis SLR(1)</summary><p>P: producciones originales</p><ol start="1" id="producciones-originales">${slr.producciones.slice(1).map(([izq, der]) => `<li><code>${e(izq)} → ${e(der.join(" ") || "ε")}</code></li>`).join("")}</ol><p>G = (N, T, P, S). S = ${e(slr.inicial)}. N = { ${e(slr.no_terminales.join(", "))} }. T = { ${e(slr.terminales.join(", "))} }.</p><p id="produccion-aumentada">Producción aumentada (0), fuera de P: <code>${e(aumentado)} → ${e(derecha.join(" "))}</code></p><p>Analizador SLR(1): ${slr.estados.length} estados; ${slr.conflictos.length} conflictos.</p><p>dN: desplazar al estado N. rN: reducir por la producción N. $: fin del programa. Conflictos SLR: ${slr.conflictos.length}.</p>`;
        const terminales = [...slr.terminales, "$"], noTerminales = slr.no_terminales;
        html += '<details><summary>Tablas ACTION y GOTO</summary><h4>ACTION</h4>';
        html += tablaHTML(["Estado", ...terminales.map(s => s === "PUNTO_Y_COMA" ? "PYC" : s)], slr.estados.map((_, i) => ["I" + i, ...terminales.map(s => slr.acciones[i][s] ?? "")]), "tabla-slr");
        html += '<h4>GOTO</h4>' + tablaHTML(["Estado", ...noTerminales], slr.estados.map((_, i) => ["I" + i, ...noTerminales.map(s => slr.saltos[i][s] ?? "")]), "tabla-slr");
        html += '</details><details><summary>FIRST y FOLLOW</summary>';
        html += "<h3>FIRST y FOLLOW</h3>" + tablaHTML(["No terminal", "FIRST", "FOLLOW"], noTerminales.map(s => [s, slr.primeros[s].join(", "), slr.siguientes[s].join(", ")]));
        html += "</details><details><summary>Ítems y transiciones LR(0)</summary><h3>Transiciones LR(0)</h3>" + tablaHTML(["Origen", "Símbolo", "Destino"], slr.transiciones.map(t => ["I" + t.origen, t.simbolo, "I" + t.destino]));
        slr.estados.forEach((items, i) => {
            html += `<h3>I${i}</h3><ul>${items.map(([p, punto]) => {
                const [izq, der] = slr.producciones[p];
                return `<li><code>${e(izq)} → ${e([...der.slice(0, punto), "·", ...der.slice(punto)].join(" "))}</code></li>`;
            }).join("")}</ul>`;
        });
        html += "</details><details><summary>Derivación y traza SLR(1)</summary>";
        for (const r of resultado.registros) {
            if (r.arbol) html += `<h3>Derivación por la izquierda del programa completo</h3><ol>${r.derivacion.map(p => `<li><code>${e(p.join(" "))}</code></li>`).join("")}</ol>`;
            if (r.traza.length) html += `<h3>Traza SLR(1) del programa completo</h3>` + tablaHTML(["Pila de estados", "Entrada", "Acción"], r.traza.map(p => [p.pila.join(" "), p.entrada.join(" "), p.accion]));
        }
        return html + "</details></details></div></section>";
    }
    function renderizar(resultado, automatas, config = {}) {
        const {tokens, errores} = resultado;
        let html = renderizarSalida(resultado) + '<section id="proceso-interno"><h2>C. Proceso interno</h2><section id="analisis-lexico"><h3>C.1 Análisis léxico</h3>';
        html+='<p>Las cinco familias son seleccionables para estudiar sus autómatas. Los literales también son tokens del analizador.</p>';
        html+=tablaHTML(["Token","Descripción","Expresión regular","Ejemplos léxicos válidos / inválidos"],Object.entries(automatas).map(([n,d])=>[n,config.descripciones?.[n]??n,d.expresion,d.ejemplos[0].join(" / ")+(n === "IGUAL" ? "; No como IGUAL: " : "; No: ")+d.ejemplos[1].join(" / ")]));
        html+=`<p class="nota">Literales: ${Object.entries(config.literales || {}).map(([l,n]) => `<code>${e(l)}</code> (${e(n)})`).join("; ")}.</p><h4>Lexemas de la entrada</h4>`;
        if (tokens.length) {
            const filas = tokens.map(t => [t.linea, t.columna, t.lexema, t.token, automatas[t.token]?.expresion ?? t.lexema]);
            const columnas = ["Línea", "Columna", "Lexema", "Token", "Expresión regular"];
            html += tablaHTML(columnas, filas.slice(0,6)) + `<details><summary>Ver todos los lexemas (${tokens.length})</summary>` + tablaHTML(columnas, filas) + "</details>";
        }
        if (errores.length) html += '<h3 class="error">Errores léxicos</h3>' + errores.map(t => `<p>Línea ${t.linea}, columna ${t.columna}: <strong>${e(t.lexema)}</strong> ${e(t.detalle)}</p>`).join("");
        else html += '<p class="correcto">Análisis léxico completado sin errores.</p>';
        if (!tokens.length) html += "<p>No se reconocieron tokens válidos.</p>";
        html += '<div class="automatas-lexicos"><h4>Expresiones regulares y autómatas</h4><p>Selecciona una familia. Un AFND directo puede ser determinista: en ese caso AFND y AFD reconocen con la misma estructura. El mínimo se calcula por particiones.</p><div class="selector">';
        for (const nombre of Object.keys(automatas)) html += `<button type="button" class="boton-token" data-token="${nombre}" onclick="seleccionarToken('${nombre}')">${nombre}</button>`;
        html += "</div>";
        for (const [nombre, datos] of Object.entries(automatas)) {
            html += `<div class="panel-token" id="token-${nombre}"><div class="panel"><h3>${nombre}</h3><p><strong>Expresión regular:</strong> <code>${e(datos.expresion)}</code></p><p>${Object.entries(tipos).map(([t, titulo]) => `<span class="etiqueta">${titulo}: ${datos[t].estados.length} estados${t === "afd_minimo" ? " (sin sumidero explícito)" : ""}</span>`).join(" ")}</p></div><p>Cumplen la expresión regular: ${e(datos.ejemplos[0].join(" / "))}. Inválidos: ${e(datos.ejemplos[1].join(" / "))}.</p><div class="comparacion-automatas">`;
            for (const tipo of Object.keys(tipos)) {
                const panel = panelAutomata(nombre, tipo, datos);
                html += tipo === "afd_minimo" ? `<details class="automata-minimo" ontoggle="if (this.open) reiniciarZoom('grafico-${nombre}-afd_minimo')"><summary>Consultar AFD mínimo parcial (sin sumidero explícito)</summary>${panel}</details>` : panel;
            }
            html += "</div></div>";
        }
        return html + "</div></section>" + renderizarSintaxis(resultado) + renderizarSemantica(resultado) + "</section>";
    }
    const vistas = {dibujar, renderizar};
    if (typeof module !== "undefined" && module.exports) module.exports = vistas;
    else global.VistasAnalizador = vistas;
})(globalThis);
