const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const {test} = require("node:test");
const motor = require("./netlify-public/motor.js");
const vistas = require("./netlify-public/vistas.js");
const clinica = require("./netlify-public/clinica.js");
const carpeta = path.resolve("netlify-public");
const pagina = fs.readFileSync(path.join(carpeta, "index.html"), "utf8");
const config = JSON.parse(pagina.match(/<script id="lenguaje-config" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const automatas = motor.generarTodos(config);

function clases() {
    const valores = new Set();
    return {add: v => valores.add(v), remove: v => valores.delete(v), contains: v => valores.has(v)};
}

// DOM acotado a los controles existentes. Se ejecutan los scripts reales del build.
function entorno() {
    const eventos = {}, boton = {disabled: false}, estado = {};
    const entrada = {texto: pagina.match(/<textarea[^>]*>([\s\S]*?)<\/textarea>/)[1].replaceAll("&gt;", ">").replaceAll("&lt;", "<").replaceAll("&amp;", "&"), archivo: null};
    let graficos = [], botones = [], paneles = [], detalles = [], html = "", peticiones = 0;
    const texto = {get value() {return entrada.texto;}, set value(v) {entrada.texto = v;}};
    const resultados = {
        get innerHTML() {return html;},
        set innerHTML(v) {
            html = v;
            detalles = [...v.matchAll(/<details([^>]*)>/g)].map(m => ({open: /\bopen\b/.test(m[1])}));
            graficos = [...v.matchAll(/class="grafico" id="([^"]+)"[^>]*><svg[^>]*viewBox="0 0 ([\d.]+) ([\d.]+)"/g)].map(m => {
                const imagen = {dataset: {}, style: {}, viewBox: {baseVal: {width: Number(m[2]), height: Number(m[3])}}};
                return {id: m[1], scrollLeft: 0, scrollTop: 0, querySelector: () => imagen};
            });
            botones = [...v.matchAll(/class="boton-token" data-token="([^"]+)"/g)].map(m => ({dataset: {token: m[1]}, classList: clases()}));
            paneles = [...v.matchAll(/class="panel-token" id="([^"]+)"/g)].map(m => ({id: m[1], classList: clases(), automatas: ["afnd", "afd", "afd_minimo"].map(tipo => ({dataset: {tipo}, hidden: false}))}));
        }
    };
    const formulario = {querySelector: () => boton, addEventListener: (nombre, fn) => eventos[nombre] = fn};
    const document = {
        getElementById(id) {
            if (id === "lenguaje-config") return {textContent: JSON.stringify(config)};
            if (id === "texto") return texto;
            if (id === "resultados") return resultados;
            if (id === "estado-conexion") return estado;
            return [...graficos, ...paneles].find(n => n.id === id);
        },
        querySelector(selector) {
            if (selector === "form") return formulario;
            if (selector === ".boton-token") return botones[0];
            return botones.find(b => selector.includes('"' + b.dataset.token + '"'));
        },
        querySelectorAll(selector) {
            if (selector === "details") return detalles;
            if (selector === ".grafico") return graficos;
            if (selector === ".panel-token") return paneles;
            if (selector === ".boton-token") return botones;
            if (selector.includes(".panel-automata")) return paneles.find(p => selector.startsWith("#" + p.id + " ")).automatas;
            throw new Error("Selector inesperado: " + selector);
        }
    };
    const sinRed = () => {peticiones++; throw new Error("Red bloqueada en esta prueba");};
    const contexto = {document, FormData: class {get(nombre) {return entrada[nombre];}}, TextEncoder, TextDecoder,
        fetch: sinRed, XMLHttpRequest: sinRed, WebSocket: sinRed, console, addEventListener: (nombre, fn) => eventos[nombre] = fn};
    contexto.window = contexto;
    vm.createContext(contexto);
    for (const script of pagina.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)) {
        if (script[1].includes('type="application/json"')) continue;
        const src = script[1].match(/src="([^"]+)"/);
        if (src) {
            assert.match(src[1], /^\/[a-z]+\.js$/);
            vm.runInContext(fs.readFileSync(path.join(carpeta, src[1].slice(1)), "utf8"), contexto, {filename: src[1]});
        } else vm.runInContext(script[2], contexto);
    }
    return {contexto, eventos, boton, estado, resultados, entrada, document, peticiones: () => peticiones};
}
const compilar = entorno => entorno.eventos.submit({preventDefault() {}});
const archivo = (name, contenido) => {
    const bytes = typeof contenido === "string" ? new TextEncoder().encode(contenido) : contenido;
    return {name, size: bytes.byteLength, arrayBuffer: async () => bytes.buffer};
};


function acepta(a, cadena) {
    let estados = motor.cierre([a.inicial], a.transiciones);
    for (const c of cadena) estados = motor.cierre(a.transiciones.filter(t => estados.includes(t.origen) && motor.expandir(t.simbolo).includes(c)).map(t => t.destino), a.transiciones);
    return estados.some(e => a.finales.includes(e));
}

test("Thompson genera expresiones nuevas y rechaza sintaxis no admitida", () => {
    const a = motor.crearAFND("Z(a|b)+[0-2]?");
    for (const s of ["Za", "Zabb2", "Zbbb0"]) assert.equal(acepta(a, s), true);
    for (const s of ["Z", "Za3", "Zc", "Zab00"]) assert.equal(acepta(a, s), false);
    for (const p of ["[z-a]", "[", "(a", "a{3,2}", "a{,2}", "a{1", "[^a]", "\\d", ".", "a**"]) assert.throws(() => motor.crearAFND(p));
    assert.match(vistas.dibujar(a, "nuevo"), /data-estado="q/);
});

test("Selección de los cinco tokens, tipos y zoom usan los controles originales", async () => {
    const t = entorno(); await compilar(t);
    for (const nombre of Object.keys(config.expresiones)) {
        t.contexto.seleccionarToken(nombre);
        assert.equal(t.document.getElementById("token-" + nombre).classList.contains("activo"), true);
        for (const tipo of ["afnd", "afd", "afd_minimo"]) {
            t.contexto.seleccionarTipo(nombre, tipo);
            const paneles = t.document.querySelectorAll("#token-" + nombre + " .panel-automata");
            assert.deepEqual(paneles.map(p => p.hidden), paneles.map(p => p.dataset.tipo !== tipo));
            const id = "grafico-" + nombre + "-" + tipo, g = t.document.getElementById(id), imagen = g.querySelector("svg");
            t.contexto.cambiarZoom(id, 1.25);
            assert.equal(imagen.style.width, imagen.viewBox.baseVal.width * 1.25 + "px");
            t.contexto.cambiarZoom(id, 0.8);
            assert.equal(imagen.style.width, imagen.viewBox.baseVal.width + "px");
            t.contexto.cambiarZoom(id, 100); assert.equal(imagen.dataset.escala, 4);
            t.contexto.cambiarZoom(id, 0.001); assert.equal(imagen.dataset.escala, 0.5);
            g.scrollLeft = 70; t.contexto.reiniciarZoom(id);
            assert.equal(imagen.dataset.escala, 1); assert.equal(g.scrollLeft, 0);
        }
    }
});

test("El marco SVG incluye contenido desbordado sin acumular márgenes", () => {
    const t = entorno();
    const imagen = {
        dataset: {}, viewBox: {baseVal: {x: 0, y: 0, width: 300, height: 200}},
        getBBox: () => ({x: -15, y: -8, width: 340, height: 230}),
        setAttribute: (nombre, valor) => { imagen.marco = valor; }
    };
    t.contexto.ajustarMarcoSVG(imagen);
    assert.equal(imagen.marco, "-39 -32 388 278");
    t.contexto.ajustarMarcoSVG(imagen);
    assert.equal(imagen.marco, "-39 -32 388 278");
    const oculto = {dataset: {}, getBBox: () => ({width: 0, height: 0})};
    t.contexto.ajustarMarcoSVG(oculto);
    assert.equal(oculto.dataset.marco, undefined);
});

test("Tamaño natural inicial de los quince autómatas conserva proporción y zoom manual", async () => {
    const t = entorno(); await compilar(t);
    for (const g of t.document.querySelectorAll(".grafico")) {
        const svg = g.querySelector("svg"), {width, height} = svg.viewBox.baseVal;
        g.clientWidth = width * 0.9;
        t.contexto.reiniciarZoom(g.id);
        assert.equal(svg.dataset.escala, 1);
        assert.equal(svg.style.width, width + "px");
        assert.equal(svg.style.height, height + "px");
        g.clientWidth = width * 0.2;
        t.contexto.ajustarGraficosAlAncho();
        assert.equal(svg.dataset.escala, 1);
        t.contexto.cambiarZoom(g.id, 2);
        g.clientWidth = width * 2;
        t.contexto.ajustarGraficosAlAncho();
        assert.equal(svg.dataset.escala, 2);
        t.contexto.reiniciarZoom(g.id);
        assert.equal(svg.dataset.escala, 1);
        assert.equal(svg.style.height, height + "px");
        g.clientWidth = 0;
        assert.equal(t.contexto.escalaInicial(g, svg), 1);
    }
});



const ejemplo="CARGAR S01 = 28;\nCARGAR S02 = 15;\nSI S01 > 26 Y S02 < 20 ENTONCES AVISAR A01;";
const simulador=require("./netlify-public/simulador.js");
function programa(valor=28,op=">",umbral=26,accion="A01"){return `CARGAR S01=${valor}; SI S01 ${op} ${umbral} ENTONCES AVISAR ${accion};`;}
function jsonVisible(html){return JSON.parse(html.match(/<pre id="salida-json"[^>]*>([\s\S]*?)<\/pre>/)[1].replaceAll("&quot;",'"').replaceAll("&lt;","<").replaceAll("&gt;",">").replaceAll("&amp;","&"));}

test("Programa válido: SLR real, traducción exacta y A01 ejecutado",()=>{
    const r=clinica.compilar(ejemplo,config);
    assert.equal(r.aceptado,true);
    assert.equal(r.slr.estados.length,27);assert.deepEqual(r.slr.conflictos,[]);
    assert.equal(r.registros[0].traza.at(-1).accion,"aceptar");
    assert.deepEqual(r.salida,{estado:"aceptado",avisos:[{codigo:"A01",descripcion:config.acciones.A01}]});
    assert.equal(r.codigo.map(c=>c.op+(c.arg===undefined?"":" "+c.arg)).join("\n"),"PUSH 28\nSTORE S01\nPUSH 15\nSTORE S02\nLOAD S01\nPUSH 26\nGT\nJUMP_IF_FALSE L1\nLOAD S02\nPUSH 20\nLT\nJUMP_IF_FALSE L1\nEMIT A01\nLABEL L1");
});
test("Condición falsa válida con cortocircuito y sin aviso",()=>{
    const r=clinica.compilar(ejemplo.replace("28","20").replace("15","80"),config);
    assert.equal(r.aceptado,true);assert.deepEqual(r.salida.avisos,[]);assert.equal(r.simulacion.ejecutadas.includes(8),false);
});
test("Reconocimiento atómico, literales, comparación y asignación",()=>{
    for(const lexema of ["S011","SIEMPRE","!","A011","s01","28.5","1x","__proto__"]){
        const r=clinica.analizar(lexema,config);assert.deepEqual(r.tokens,[]);assert.equal(r.errores[0].lexema,lexema);
    }
    assert.deepEqual(clinica.analizar("===",config).tokens.map(t=>t.lexema),["==","="]);
    const {tokens,errores}=clinica.analizar("CARGAR S99=1; SI S99==1 ENTONCES AVISAR A99;",config);
    assert.deepEqual(errores,[]);assert.equal(tokens[2].token,"IGUAL");assert.equal(tokens[7].token,"COMPARADOR");assert.equal(tokens[4].token,"PUNTO_Y_COMA");
});
test("Cada error rechaza todo el programa sin traducción ni ejecución parcial",()=>{
    const entradas=[programa()+" !",programa().replace("=28","28"),programa().replaceAll("S01","S99"),programa()+" SI S01>26 ENTONCES AVISAR A99;",programa(51),programa().replace("SI S01","SI S02"),"CARGAR S01=20; "+programa(),programa()+" CARGAR S02=10;",programa().replace("28","9".repeat(400))];
    for(const texto of entradas){const r=clinica.compilar(texto,config);assert.equal(r.aceptado,false,texto);assert.equal(r.simulacion,null);assert.equal(r.salida,null);assert.deepEqual(r.codigo,[]);}
});
test("Comparadores y varias reglas conservan orden y resultados",()=>{
    for(const [op,u,esperado] of [[">",26,true],["<",26,false],[">=",28,true],["<=",28,true],["==",28,true],["!=",28,false]]){
        const r=clinica.compilar(programa(28,op,u),config);assert.equal(r.aceptado,true);assert.equal(!!r.salida.avisos.length,esperado);
    }
    const r=clinica.compilar(programa()+" SI S01<30 ENTONCES AVISAR A02;",config);
    assert.deepEqual(r.salida.avisos.map(a=>a.codigo),["A01","A02"]);
    const codigo=structuredClone(r.codigo);codigo[0].arg=20;
    assert.deepEqual(simulador.ejecutar(codigo,config).avisos.map(a=>a.codigo),["A02"]);
});
test("Simulador independiente rechaza opcodes, pila y saltos inválidos",()=>{
    for(const codigo of [[],[{op:"EXEC",arg:"x"}],[{op:"GT"}],[{op:"LOAD",arg:"S01"}],[{op:"PUSH",arg:1}],[{op:"JUMP_IF_FALSE",arg:"L9"}],[{op:"LABEL",arg:"L1"},{op:"JUMP_IF_FALSE",arg:"L1"}]])assert.throws(()=>simulador.ejecutar(codigo,config));
});
test("Frontend generado funciona sin red: código, JSON y quince SVG reales",async()=>{
    const t=entorno();t.entrada.texto=ejemplo;await compilar(t);
    assert.equal(t.peticiones(),0);assert.equal(t.boton.disabled,false);assert.match(t.estado.textContent,/completado en este navegador/);
    assert.deepEqual(jsonVisible(t.resultados.innerHTML),{estado:"aceptado",avisos:[{codigo:"A01",descripcion:config.acciones.A01}]});
    assert.match(t.resultados.innerHTML,/STORE S01/);assert.match(t.resultados.innerHTML,/<h4>ACTION<\/h4>/);assert.match(t.resultados.innerHTML,/<th>PYC<\/th>/);
    assert.equal(t.document.querySelectorAll(".grafico").length,15);assert.equal(t.document.querySelectorAll(".boton-token").length,5);
});
test("TXT con BOM y programa mixto rechaza sin conservar un JSON exitoso anterior",async()=>{
    const t=entorno();t.entrada.archivo=archivo("valido.txt","\ufeff"+ejemplo);await compilar(t);
    assert.equal(t.entrada.texto,ejemplo);assert.equal(jsonVisible(t.resultados.innerHTML).estado,"aceptado");
    t.entrada.archivo=archivo("mixto.txt",ejemplo+"\nSI S01>0 ENTONCES AVISAR A99;");await compilar(t);
    assert.match(t.resultados.innerHTML,/Programa rechazado/);assert.doesNotMatch(t.resultados.innerHTML,/id="salida-json"/);assert.match(t.resultados.innerHTML,/A99/);assert.equal(t.peticiones(),0);
});
test("Árbol, atributos y salida cambian con la entrada",async()=>{
    const t=entorno();t.entrada.texto=programa();await compilar(t);const antes=t.resultados.innerHTML;
    t.entrada.texto=programa(20);await compilar(t);
    assert.notEqual(t.resultados.innerHTML,antes);assert.deepEqual(jsonVisible(t.resultados.innerHTML).avisos,[]);
    assert.match(t.resultados.innerHTML,/PUSH 20/);assert.match(t.resultados.innerHTML,/<td>20<\/td>/);
});
test("Extensión, UTF8, tamaño y vacío liberan el botón sin ejecutar",async()=>{
    for(const a of [archivo("x.csv",ejemplo),archivo("x.txt",new Uint8Array([255])),{name:"x.txt",size:config.limite+1}]){
        const t=entorno();t.entrada.archivo=a;await compilar(t);assert.equal(t.boton.disabled,false);assert.equal(t.resultados.innerHTML,"");assert.equal(t.peticiones(),0);
    }
    const t=entorno();t.entrada.texto=" ";await compilar(t);assert.match(t.estado.textContent,/Introduce instrucciones/);
});
test("Autómatas directos, ejemplos y equivalencia AFND–AFD–mínimo",()=>{
    function acepta(a,s){let estados=motor.cierre([a.inicial],a.transiciones);for(const c of s)estados=motor.cierre(a.transiciones.filter(t=>estados.includes(t.origen)&&motor.expandir(t.simbolo).includes(c)).map(t=>t.destino),a.transiciones);return estados.some(e=>a.finales.includes(e));}
    for(const d of Object.values(automatas)){
        for(const [i,grupo] of d.ejemplos.entries())for(const s of grupo)for(const tipo of ["afnd","afd","afd_minimo"])assert.equal(acepta(d[tipo],s),i===0);
        for(const b of [d.afd,d.afd_minimo,motor.convertirAFD(motor.crearAFND(d.expresion))]){
            const cola=[[motor.cierre([d.afnd.inicial],d.afnd.transiciones),b.inicial]],vistos=new Set();
            for(let i=0;i<cola.length;i++){
                const [grupo,e]=cola[i],k=JSON.stringify([grupo,e]);if(vistos.has(k))continue;vistos.add(k);
                assert.equal(grupo.some(q=>d.afnd.finales.includes(q)),b.finales.includes(e));
                for(const s of motor.alfabeto(d.afnd))cola.push([motor.cierre(d.afnd.transiciones.filter(t=>grupo.includes(t.origen)&&motor.expandir(t.simbolo).includes(s)).map(t=>t.destino),d.afnd.transiciones),b.transiciones.find(t=>t.origen===e&&t.simbolo===s)?.destino??null]);
            }
        }
    }
});
test("SLR genérico mantiene epsilon, símbolo fresco y detección de conflictos",()=>{
    const m=clinica.generarSLR({inicial:"S",producciones:[["S",["A","b"]],["A",[]],["A",["a"]]]});
    assert.equal(clinica.analizarSintaxis([{token:"b",lexema:"b",linea:1,columna:1}],m).aceptado,true);
    assert.throws(()=>clinica.generarSLR({inicial:"S",producciones:[["S",["S","S"]],["S",["a"]]]}),/Conflicto/);
    assert.deepEqual(clinica.generarSLR({inicial:"S",producciones:[["S",["S'"]],["S'",["a"]]]}).producciones[0],["S''",["S"]]);
});


test("Los lexemas HTML se escapan y una nueva compilación se recupera de errores",async()=>{
    const t=entorno();t.entrada.texto='<img/src=x/onerror=alert(1)>';await compilar(t);
    assert.doesNotMatch(t.resultados.innerHTML,/<img/);assert.match(t.resultados.innerHTML,/&lt;/);
    assert.doesNotMatch(t.resultados.innerHTML,/id="salida-json"/);
    t.entrada.texto=ejemplo;await compilar(t);
    assert.equal(jsonVisible(t.resultados.innerHTML).avisos[0].codigo,"A01");assert.equal(t.boton.disabled,false);
});


test("La impresión abre toda la evidencia y restaura los desplegables", async () => {
    const t = entorno(); await compilar(t);
    const detalles = t.document.querySelectorAll("details");
    const estados = detalles.map(d => d.open);
    assert.ok(estados.some(Boolean)); assert.ok(estados.some(v => !v));
    t.eventos.beforeprint(); assert.ok(detalles.every(d => d.open));
    t.eventos.beforeprint();
    t.eventos.afterprint(); assert.deepEqual(detalles.map(d => d.open), estados);
    t.eventos.afterprint(); assert.deepEqual(detalles.map(d => d.open), estados);
});

test("Presentación progresiva conserva IR dinámico, errores y todos los lexemas", async () => {
    const t = entorno(); await compilar(t);
    let html = t.resultados.innerHTML;
    assert.match(html, /Derivación por la izquierda del programa completo/);
    assert.match(html, /Traza SLR\(1\) del programa completo/);
    assert.match(html, /Revisión técnica simulada/);
    assert.match(html, /AFD mínimo: 4 estados/);
    assert.match(html, /1 aviso;/); assert.doesNotMatch(html, /1 avisos/);
    assert.match(html, /<details><summary>Ver código intermedio \(14 instrucciones\)<\/summary>/);
    assert.match(html, /<details><summary>Ver todos los lexemas \(22\)<\/summary>/);
    assert.match(html, /<details><summary>Ver comprobaciones semánticas<\/summary>/);
    assert.equal((html.match(/class="tabla-slr"/g)||[]).length, 2);
    assert.doesNotMatch(html, /sumidero/);
    const ejemplo = t.entrada.texto;
    t.entrada.texto = ejemplo + "\nSI S01 > 0 ENTONCES AVISAR A02;";
    await compilar(t); html = t.resultados.innerHTML;
    assert.match(html, /2 avisos;/);
    const r = clinica.compilar(t.entrada.texto,config);
    assert.ok(html.includes(`Ver código intermedio (${r.codigo.length} instrucciones)`));
    t.entrada.texto = ejemplo.replace("28", "99"); await compilar(t);
    html = t.resultados.innerHTML;
    assert.match(html, /Error semántico/); assert.doesNotMatch(html, /id="salida-json"/);
});


test("Catálogo único y regex reales de los once tokens; exportaciones accesibles", async () => {
    const t = entorno(); await compilar(t);
    const html = t.resultados.innerHTML;
    const catalogo = html.slice(html.indexOf("<table"),html.indexOf("</table>")+8);
    const nombres = [...catalogo.matchAll(/<tr><td>([^<]+)<\/td>/g)].map(m=>m[1]);
    assert.equal(nombres.length,11); assert.equal(new Set(nombres).size,11);
    for (const token of Object.keys(config.patrones_tokens)) assert.ok(nombres.includes(token));
    const resultado = clinica.compilar(t.entrada.texto,config);
    assert.equal(resultado.tokens.length,22);
    for (const t of resultado.tokens) assert.ok(new RegExp("^(?:"+config.patrones_tokens[t.token]+")$").test(t.lexema));
    assert.match(html,/href="\/jflap\/CARGAR-afnd.jff"/);
    assert.match(html,/href="\/jflap\/SENSOR-afd_minimo.jff"/);
    for (const d of Object.values(automatas)) for (const tipo of ["afnd","afd","afd_minimo"])
        for (const arista of d[tipo].transiciones) assert.ok(arista.simbolo === "ε" || [...arista.simbolo].length === 1);
    assert.match(html,/<div class="arbol-oculto" hidden>/);
    assert.match(html,/<div id="gramatica" hidden>/);
    assert.ok(html.indexOf("2. Análisis léxico")<html.indexOf("3. Análisis sintáctico y semántico"));
    assert.ok(html.indexOf("3. Análisis sintáctico y semántico")<html.indexOf("4. Resultado"));
});


test("Etiquetas verticales conservan letras, espacio y epsilon individuales", async () => {
    const simbolos = ["a", "b", "c", " ", "\u03b5"];
    const modelo = {estados: ["q0", "q1"], inicial: "q0", finales: ["q1"],
        transiciones: simbolos.map(simbolo => ({origen: "q0", destino: "q1", simbolo}))};
    const svg = vistas.dibujar(modelo, "prueba");
    const lineas = [...svg.matchAll(/<tspan x="([^"]+)" y="([^"]+)">([^<]+)<\/tspan>/g)];
    assert.deepEqual(lineas.map(m => m[3]), ["\u2420", "a", "b", "c", "\u03b5"]);
    assert.equal(new Set(lineas.map(m => m[1])).size, 1);
    for (let i = 1; i < lineas.length; i++) assert.equal(+lineas[i][2] - +lineas[i-1][2], 15);
    assert.equal(modelo.transiciones.length, simbolos.length);
    const t = entorno(); await compilar(t);
    const html = t.resultados.innerHTML;
    assert.ok(!html.includes("Consultar AFD"));
    assert.equal((html.match(/<summary>AFD m\u00ednimo<\/summary>/g) || []).length, 5);
});
