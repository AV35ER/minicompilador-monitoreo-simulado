(function(global) {
"use strict";
const slr=typeof module!=="undefined"&&module.exports?require("./slr.js"):global.SLR;
const vm=typeof module!=="undefined"&&module.exports?require("./simulador.js"):global.Simulador;
const espacios=/[\t-\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/u;
const lineas=texto=>texto.split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/u);
const operadores={">":"GT","<":"LT",">=":"GE","<=":"LE","==":"EQ","!=":"NE"};
function contieneDatos(texto){return [...texto].some(c=>!espacios.test(c));}
function analizar(texto,config) {
    const tokens=[],errores=[];
    const reglas=Object.entries(config.patrones_tokens || config.expresiones).map(([n,p])=>[n,new RegExp("^(?:"+p+")$")]);
    lineas(texto).forEach((linea,i)=>{
        const caracteres=[...linea];
        for(let pos=0;pos<caracteres.length;) {
            if(espacios.test(caracteres[pos])){pos++;continue;}
            const inicio=pos;
            if(caracteres[pos]===";") pos++;
            else if("=<>!".includes(caracteres[pos])) pos += ["<=",">=","==","!="].includes(caracteres.slice(pos,pos+2).join("")) ? 2 : 1;
            else while(pos<caracteres.length&&!espacios.test(caracteres[pos])&&!";=<>!".includes(caracteres[pos]))pos++;
            const lexema=caracteres.slice(inicio,pos).join("");
            const token=config.patrones_tokens ? reglas.find(([,p])=>p.test(lexema))?.[0] : (Object.hasOwn(config.literales,lexema)?config.literales[lexema]:reglas.find(([,p])=>p.test(lexema))?.[0]);
            const e={linea:i+1,columna:inicio+1,lexema};
            if(token)tokens.push({...e,token});else errores.push({...e,detalle:"Lexema no reconocido; respeta códigos completos, operadores y mayúsculas."});
        }
    });return {tokens,errores};
}
function reducir(izquierda,a) {
    if(izquierda==="P")return {cargas:a[0],reglas:a[1]};
    if(izquierda==="CARGAS"||izquierda==="REGLAS")return [a[0],...(a.length===2?a[1]:[])];
    if(izquierda==="CARGA")return {sensor:a[1].lexema,valor:a[3].lexema,linea:a[1].linea,columna:a[1].columna,columna_valor:a[3].columna};
    if(izquierda==="REGLA")return {comparaciones:a[1],accion:a[4].lexema,linea:a[4].linea,columna:a[4].columna};
    if(izquierda==="COND")return [a[0],...a[1]];
    if(izquierda==="RESTO")return a.length?[a[1],...a[2]]:[];
    return {sensor:a[0].lexema,comparador:a[1].lexema,valor:a[2].lexema,linea:a[0].linea,columna:a[0].columna,columna_valor:a[2].columna};
}
function validarSemantica(programa,config) {
    const atributos=[],errores=[],cargados=new Set();
    function comprobar(campo,lexema,tipo,accion,valido,e,columna) {
        atributos.push({campo,lexema,tipo,accion,valido,linea:e.linea});
        if(!valido)errores.push({linea:e.linea,columna:columna||e.columna,lexema,detalle:accion+": "+lexema});
    }
    function sensorValor(e,carga) {
        const sensor=e.sensor,conocido=Object.hasOwn(config.sensores,sensor);
        comprobar("sensor",sensor,"sensor","Código de sensor conocido",conocido,e);
        comprobar("referencia",sensor,"referencia",carga?"Carga única":"Sensor cargado previamente",carga?!cargados.has(sensor):cargados.has(sensor),e);
        const normal=e.valor.replace(/^0+/,"")||"0",valor=normal.length<=3?Number(normal):1000;
        const valido=conocido&&valor>=config.sensores[sensor].minimo&&valor<=config.sensores[sensor].maximo;
        comprobar("valor",e.valor,"entero","Valor dentro del rango del sensor",valido,e,e.columna_valor);
        if(carga)cargados.add(sensor);
    }
    for(const carga of programa.cargas)sensorValor(carga,true);
    for(const regla of programa.reglas) {
        for(const c of regla.comparaciones){sensorValor(c,false);comprobar("comparador",c.comparador,"operador","Comparador permitido",Object.hasOwn(operadores,c.comparador),c);}
        comprobar("accion",regla.accion,"accion","Código de acción conocido",Object.hasOwn(config.acciones,regla.accion),regla);
    }return {atributos,errores};
}
function traducir(programa) {
    const codigo=[],correspondencias=[];
    for(const c of programa.cargas)codigo.push({op:"PUSH",arg:Number(c.valor)},{op:"STORE",arg:c.sensor});
    programa.reglas.forEach((regla,i)=>{
        const inicio=codigo.length,etiqueta="L"+(i+1);
        for(const c of regla.comparaciones)codigo.push({op:"LOAD",arg:c.sensor},{op:"PUSH",arg:Number(c.valor)},{op:operadores[c.comparador]},{op:"JUMP_IF_FALSE",arg:etiqueta});
        codigo.push({op:"EMIT",arg:regla.accion},{op:"LABEL",arg:etiqueta});
        correspondencias.push({regla:i+1,linea:regla.linea,inicio,fin:codigo.length-1,etiqueta});
    });return {codigo,correspondencias};
}
let cacheGramatica,cacheSLR;
function compilar(texto,config) {
    const clave=JSON.stringify(config.gramatica);
    if(clave!==cacheGramatica){cacheSLR=slr.generarSLR(config.gramatica);cacheGramatica=clave;}
    let {tokens,errores}=[...texto].length>config.limites.caracteres
        ?{tokens:[],errores:[{linea:1,columna:1,lexema:"",detalle:"Límite de entrada: 65536 caracteres."}]}:analizar(texto,config);
    if(tokens.length>config.limites.tokens){errores.push({linea:1,columna:1,lexema:"",detalle:"Límite de 300 tokens excedido."});tokens=tokens.slice(0,config.limites.tokens);}
    const r=errores.length?{aceptado:false,arbol:null,derivacion:[],traza:[],estructura:null,errores_sintacticos:[]}:slr.analizarSintaxis(tokens,cacheSLR,reducir);
    Object.assign(r,{linea:1,sintaxis_aceptada:r.aceptado,fase:errores.length?"léxico":"sintáctico",atributos:[],errores_semanticos:[],salida:null});
    let codigo=[],correspondencias=[],simulacion=null;
    if(r.aceptado) {
        const sem=validarSemantica(r.estructura,config);r.atributos=sem.atributos;r.errores_semanticos=sem.errores;
        if(r.estructura.cargas.length+r.estructura.reglas.length>config.limites.instrucciones)r.errores_semanticos.push({linea:1,columna:1,detalle:"Límite de 50 instrucciones excedido."});
        r.aceptado=!r.errores_semanticos.length;r.fase=r.aceptado?"aceptado":"semántico";
        if(r.aceptado){({codigo,correspondencias}=traducir(r.estructura));simulacion=vm.ejecutar(codigo,config);r.salida={estado:"aceptado",avisos:simulacion.avisos};}
    }
    return {tokens,errores,registros:[r],aceptado:r.aceptado,slr:cacheSLR,salida:r.salida,codigo,correspondencias,simulacion};
}
const clinica={...slr,analizar,compilar,contieneDatos,traducir};
if(typeof module!=="undefined"&&module.exports)module.exports=clinica;else global.Clinica=clinica;
})(globalThis);
