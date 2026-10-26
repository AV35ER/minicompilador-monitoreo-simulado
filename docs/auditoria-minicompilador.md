# Auditoría y decisiones del minicompilador clínico

## Fuentes y alcance
Se inspeccionaron el repositorio, sus pruebas y los archivos del Escritorio:
- `11.4.-Borrador inicial del proyecto_TCOM(1).docx`.
- `70. 5 Tips proyecto Compiladores.pptx`, cinco diapositivas.
- `S06 - Avance 01 TEO COMPU.docx`.
No se encontraron PDF de teoría adicionales dentro del repositorio. No se usaron documentos de otros cursos.

La guía pide lenguaje formal, tokens, regex, AFND/AFD, quíntuplas, transiciones, gramática, análisis LR, árbol y pruebas. No menciona Thompson expresamente. El PowerPoint distingue instrucciones codificadas de datos legibles y muestra entrada, resultado y proceso interno. La nueva especificación coincide con esa distinción. No se encontró una aprobación formal del antiguo tema.

El PowerPoint también pide un reporte PDF final. La interfaz ofrece impresión/guardar PDF mediante el navegador; no se afirma que la impresión ni un PDF generado se hayan verificado visualmente. Los requisitos del informe universitario (antecedentes, formulación de variables, referencias y medición empresarial) no se inventan ni se consideran resueltos por probar el programa.

## Conservación comprobada
Antes de cambiar el dominio pasaron 50 pruebas Python, con una omitida por Gunicorn/Unix, y 22 JavaScript. Se guardaron 51 archivos de la versión médica en `docs/historico/citas-medicas`, con manifiesto SHA256. Incluye fuentes, plantillas, scripts, configuración, documentación, figuras y todas sus pruebas. La gramática médica, los ejemplos y el calendario siguen recuperables allí; no se mezclan con el nuevo lenguaje.

Se reutilizaron los motores regex/Thompson/subconjuntos/minimización, el generador LR(0)/SLR, los diagramas SVG, tablas, quíntuplas, selector, zoom, entrada TXT, límites de transporte y despliegue Flask/estático. El parser SLR se separó en `slr.py`/`slr.js` y se añadieron atributos sintetizados durante las reducciones. La aplicación ahora procesa un programa completo, no registros independientes.

## Decisiones formales
- PYC es la abreviatura documental del token PUNTO_Y_COMA.
- COMPARADOR usa `<=|>=|==|!=|<|>`: las barras escapadas de la tabla Markdown del enunciado eran separadores de alternativas, no caracteres literales.
- Los operadores se reconocen por coincidencia más larga: === produce == seguido de = y se rechaza sintácticamente en un programa. Los límites de palabra impiden fragmentar S011 y SIEMPRE.
- Los códigos S99/A99 son lexemas válidos y fallan después por diccionario.
- Se permiten ceros iniciales en NUMERO; su valor es entero decimal. Se eliminan ceros antes de convertir en Python para evitar límites de conversión de cadenas enormes.
- Los límites de cada sensor se aplican tanto a cargas como a umbrales de comparación; son convenciones académicas.
- Las transiciones ausentes rechazan; el sumidero usado para minimizar se omite en la representación parcial. Un AFND directo puede ser determinista.
- Toda validación se completa antes de generar/ejecutar código. Una condición falsa no es error. Los saltos implementan cortocircuito y son exclusivamente hacia adelante.
- Un primer fallo de las pruebas reveló que Graphviz interpretaba `<, >` como HTML. Se corrige únicamente el formateo de la etiqueta, conservando el modelo (`graphviz.nohtml`, verificado en la versión instalada 0.21 y la [documentación oficial sobre etiquetas](https://graphviz.org/doc/info/shapes.html)); la prueba compara aristas contra tablas y quíntuplas.

## Límites verificables
65536 caracteres, 300 tokens y 50 instrucciones fuente; hasta 1000 instrucciones intermedias/pasos. No hay eval, bucles de fuente, llamadas, control de hardware ni persistencia. La VM recibe solo código intermedio validado. El transporte TXT conserva UTF-8/BOM y 1 MiB; el límite lingüístico es adicional.

## Material de avance
El Word externo no se modificó. El contenido académico actualizado se prepara en `avance-etapa-2.md`, con evidencia SLR generada en `slr-generado.json`. Debe incorporarse y revisarse visualmente antes de entregar un Word final; los antecedentes de citas no prueban hipótesis sobre monitoreo simulado.
