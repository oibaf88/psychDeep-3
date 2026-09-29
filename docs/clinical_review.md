# Revisión de ingeniería de seguridad clínica

## Alcance y estado

Esta revisión fija como línea base el commit `72e8372` y describe el comportamiento propuesto para `risk-engine-v1.5`. Es una revisión documental y de ingeniería: **no constituye validación clínica, certificación de dispositivo médico ni aprobación para producción clínica**. La revisión clínica formal de umbrales, mensajes y protocolos sigue pendiente.

## Comportamiento verificable

| Ruta | Regla vigente | Resultado | Límite de interpretación |
|---|---|---:|---|
| Declaración confirmada de ideación o planificación | `N4_declaracion_ideacion_o_plan` | N4 | Prioriza revisión clínica urgente; el software no confirma por sí solo una emergencia. |
| Inferencia lingüística directa vigente | `N4_senal_linguistica_ideacion_directa` | N4 | Requiere valoración humana urgente y conserva evidencia/traza. |
| Deterioro estructural extremo + rumiación alta | `N3_convergencia_critica_extrema` | N3 | Revisión profesional; no es una probabilidad de suicidio. |
| Deterioro estructural extremo + empeoramiento del sueño | `N3_convergencia_critica_extrema` | N3 | La rama de sueño es independiente de que exista una puntuación de rumiación. |

La condición N3 vigente es `adverse_composite_z > 2.4` y además (`rumination_score > 0.85` **o** empeoramiento del sueño). La tabla histórica de `MANUAL_TERAPEUTA.md` conserva su antigua N4 para que las evaluaciones previas sigan siendo interpretables; no define la lógica actual.

## Evidencia mínima antes de una validación clínica

- Probar las dos rutas N4, incluida la inferencia directa, con fallos del proveedor LLM.
- Probar por separado rumiación y sueño en la regla N3, incluidos datos ausentes.
- Evaluar una cohorte representativa que incluya casos alertados y no alertados, lenguaje ambiguo, crisis claras y variantes de consumo.
- Reportar sensibilidad, especificidad, falsos positivos, falsos negativos y calibración por subgrupo; no validar solo ejemplos seleccionados.
- Revisar explícitamente el umbral de rumiación `0.85` y el umbral estructural `2.4`; ninguna constante de detección sutil los sustituye.
- Obtener aprobación clínica humana de protocolos, recursos y texto antes de declarar el trabajo completado.

## Modelos, RAG e infraestructura

La lógica clínica es independiente del proveedor y no se atribuye capacidad clínica exclusiva a Claude ni a ningún otro modelo. La procedencia de Agent 1 registra versión y hash del prompt y del contexto cuando interviene un modelo.

Runpod permanece desactivado. El registro RAG es una base backend-only con borradores, aprobación explícita, una versión activa por destino, revisión y contraindicaciones. No está conectado al prompt ni al gateway del LLM; esa conexión exige revisión clínica, pruebas contra inyección y un rollback ensayado.
