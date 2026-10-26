# Especificación de la máquina de pila

La máquina recibe una lista finita de objetos `{op, arg}` (sin arg para comparaciones). Estado inicial: pc=0, pila vacía, memoria vacía y avisos vacíos. No recibe fuente ni árbol. Cada ejecución crea un estado nuevo.

| Instrucción | Semántica |
|---|---|
| PUSH n | Apila entero n (0–100). |
| STORE s | Desapila entero y lo asigna al sensor s, verificando su rango. |
| LOAD s | Apila el valor de un sensor inicializado. |
| GT/LT/GE/LE/EQ/NE | Desapila b y después a; apila a>b, a<b, a≥b, a≤b, a=b o a≠b. |
| JUMP_IF_FALSE L | Desapila booleano; si es falso asigna pc al índice de LABEL L, en caso contrario continúa. |
| EMIT A | Añade el aviso interpretado por el diccionario de acciones. |
| LABEL L | No cambia pila ni memoria; continúa con la siguiente instrucción. |

Todas las etiquetas son únicas y los saltos deben apuntar hacia adelante. Cada instrucción no saltada incrementa pc en uno. La pila debe terminar vacía. Los opcodes, forma de argumentos y etiquetas se comprueban antes de ejecutar; las cargas y operaciones verifican tipos en ejecución. La VM rechaza programas intermedios inválidos y no permite eval ni instrucciones externas.

El compilador traduce cada CARGAR a PUSH/STORE. Cada comparación genera LOAD/PUSH/comparador/JUMP_IF_FALSE. Todas las comparaciones de una regla saltan a la misma etiqueta posterior a EMIT: así se implementa la conjunción con cortocircuito. Regla por regla se usan etiquetas L1, L2, etc. `correspondencias` registra los índices de código de cada regla. Los índices efectivamente ejecutados y el número de pasos quedan en el resultado de simulación para comprobar cortocircuito.

Ningún código se genera si el programa fuente contiene errores léxicos, sintácticos o semánticos. La salida JSON de éxito procede exclusivamente de `avisos` de la VM. Una condición falsa produce una lista vacía sin convertir el programa en inválido.

## Objetivos ingenieriles para incorporar al avance

Objetivo general: implementar un minicompilador clínico que traduzca instrucciones de monitoreo simulado de equipos y genere avisos operativos mediante una máquina de pila.

- Definir cinco familias léxicas y seis literales para reconocer instrucciones clínicas codificadas sin fragmentaciones indebidas.
- Construir autómatas equivalentes y verificar sus transiciones, quíntuplas y lenguajes mediante pruebas automatizadas de producto.
- Generar una tabla SLR con veintisiete estados y comprobar aceptación sintáctica sin conflictos.
- Traducir programas semánticamente válidos a instrucciones intermedias y ejecutar reglas con cortocircuito en orden.
- Comparar resultados completos de Python y JavaScript y comprobar ejecución estática sin solicitudes remotas.

Estos objetivos describen la implementación, no resultados de investigación clínica. El informe final requiere revisar antecedentes, variables e hipótesis y acordar su cronograma; no se inventan métricas empresariales ni una aprobación del docente.
