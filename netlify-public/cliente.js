"use strict";

const formulario = document.querySelector("form");
const configuracion = JSON.parse(document.getElementById("lenguaje-config").textContent);
let automatasLocales;

formulario.addEventListener("submit", async evento => {
    evento.preventDefault();
    const boton = formulario.querySelector("button[type=submit]");
    const estado = document.getElementById("estado-conexion");
    const resultados = document.getElementById("resultados");
    boton.disabled = true;
    estado.hidden = false;
    estado.textContent = "Compilando en este navegador…";
    resultados.innerHTML = "";
    try {
        const datos = new FormData(formulario), archivo = datos.get("archivo");
        let texto = datos.get("texto") || "";
        if (archivo && archivo.name) {
            if (!archivo.name.toLowerCase().endsWith(".txt")) throw new Error("Selecciona un archivo TXT.");
            if (archivo.size > configuracion.limite) throw new Error("La entrada supera el máximo de 1 MiB.");
            try {texto = new TextDecoder("utf-8", {fatal: true}).decode(await archivo.arrayBuffer());}
            catch {throw new Error("El archivo debe estar codificado en UTF-8.");}
        }
        if (new TextEncoder().encode(texto).length > configuracion.limite) throw new Error("La entrada supera el máximo de 1 MiB.");
        if (!Clinica.contieneDatos(texto)) throw new Error("Introduce instrucciones o carga un archivo TXT.");
        document.getElementById("texto").value = texto;
        const resultado = Clinica.compilar(texto, configuracion);
        if (!automatasLocales) automatasLocales = MotorAutomatas.generarTodos(configuracion);
        resultados.innerHTML = VistasAnalizador.renderizar(resultado, automatasLocales, configuracion);
        inicializarResultados();
        estado.textContent = !resultado.aceptado
            ? "Análisis completado con errores. Revisa el resultado."
            : "Análisis completado en este navegador.";
    } catch (error) {
        estado.textContent = error.message || "No se pudo completar el análisis.";
    } finally {
        boton.disabled = false;
    }
});
