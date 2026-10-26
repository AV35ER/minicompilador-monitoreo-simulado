(function(global) {
"use strict";
function ejecutar(codigo, config) {
    const {sensores,acciones,limites}=config;
    if(!Array.isArray(codigo) || !codigo.length || codigo.length>limites.codigo) throw Error("Código vacío o demasiado extenso.");
    const etiquetas=new Map(), binarios={GT:(a,b)=>a>b,LT:(a,b)=>a<b,GE:(a,b)=>a>=b,LE:(a,b)=>a<=b,EQ:(a,b)=>a===b,NE:(a,b)=>a!==b};
    codigo.forEach((c,i)=>{
        if(!c || typeof c!=="object" || Array.isArray(c)) throw Error("Instrucción intermedia inválida.");
        const {op,arg}=c;
        let valido=false;
        if(Object.hasOwn(binarios,op)) valido=Object.keys(c).length===1;
        else if(op==="PUSH") valido=Number.isInteger(arg)&&arg>=0&&arg<=100;
        else if(op==="LOAD"||op==="STORE") valido=Object.hasOwn(sensores,arg);
        else if(op==="EMIT") valido=Object.hasOwn(acciones,arg);
        else if(op==="LABEL"||op==="JUMP_IF_FALSE") valido=typeof arg==="string"&&!!arg;
        if(!valido||Object.keys(c).length!==(Object.hasOwn(binarios,op)?1:2)) throw Error("Instrucción intermedia inválida.");
        if(op==="LABEL") {if(etiquetas.has(arg)) throw Error("Etiqueta duplicada."); etiquetas.set(arg,i);}
    });
    codigo.forEach((c,i)=>{if(c.op==="JUMP_IF_FALSE"&&(!etiquetas.has(c.arg)||etiquetas.get(c.arg)<=i)) throw Error("Salto desconocido o no progresivo.");});
    const pila=[],memoria={},avisos=[],ejecutadas=[];
    for(let pc=0;pc<codigo.length;) {
        if(ejecutadas.length>=limites.codigo) throw Error("Límite de ejecución excedido.");
        const {op,arg}=codigo[pc]; ejecutadas.push(pc);
        if(op==="PUSH") pila.push(arg);
        else if(op==="LOAD") {if(!Object.hasOwn(memoria,arg)) throw Error("Sensor sin inicializar.");pila.push(memoria[arg]);}
        else if(Object.hasOwn(binarios,op)) {
            if(pila.length<2||!pila.slice(-2).every(Number.isInteger)) throw Error("Pila numérica inválida.");
            const b=pila.pop(),a=pila.pop();pila.push(binarios[op](a,b));
        } else if(op==="STORE") {
            if(!Number.isInteger(pila.at(-1))||pila.at(-1)<sensores[arg].minimo||pila.at(-1)>sensores[arg].maximo) throw Error("Asignación intermedia inválida.");
            memoria[arg]=pila.pop();
        } else if(op==="JUMP_IF_FALSE") {
            if(typeof pila.at(-1)!=="boolean") throw Error("Condición intermedia inválida.");
            if(!pila.pop()){pc=etiquetas.get(arg);continue;}
        } else if(op==="EMIT") avisos.push({codigo:arg,descripcion:acciones[arg]});
        pc++;
    }
    if(pila.length) throw Error("Pila final no vacía.");
    return {memoria,avisos,pasos:ejecutadas.length,ejecutadas};
}
if(typeof module!=="undefined"&&module.exports) module.exports={ejecutar};else global.Simulador={ejecutar};
})(globalThis);
