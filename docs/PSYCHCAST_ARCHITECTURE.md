# psychcast — arquitectura objetivo y límites de seguridad

**Estado:** propuesta de arquitectura para una instancia independiente derivada de psychDeep-3. No implica que el sistema predictivo esté implementado ni validado.

## Objetivo

Crear psychcast como una nueva aplicación y entorno aislados, conservando la experiencia y los cuatro agentes LLM existentes de psychDeep. La evolución debe ser incremental: no sustituir los agentes actuales ni romper los flujos clínicos existentes.

## Reglas no negociables

1. **Aislamiento:** psychcast tendrá repositorio, servicios Render, secretos, configuración y proyecto Supabase propios. No reutilizar automáticamente las credenciales ni la base de datos de producción de psychDeep.
2. **Conservar cuatro agentes:** los cuatro agentes actuales, sus contratos, herramientas, selección de proveedor/modelo y flujos de trabajo siguen existiendo. La memoria transversal y la predicción son capas adicionales; no se deben convertir en agentes sustitutivos.
3. **Fuente de verdad clínica:** PostgreSQL/Supabase conserva los registros clínicos estructurados, consentimientos, procedencia, auditoría e historial de modelos. La memoria derivada nunca sustituye al registro original.
4. **Memoria longitudinal transversal:** capa inspirada en OpenViking/openContext para recuperar contexto útil entre conversaciones, perfiles y agentes. Almacena episodios, resúmenes, hechos, relaciones e hipótesis con enlaces a fuentes, fechas, vigencia temporal, permisos y versión.
5. **Separar hecho de inferencia:** una hipótesis generada por un LLM nunca se promueve automáticamente a hecho clínico. Las inferencias deben incluir fuente, autor/modelo, fecha, confianza y estado de revisión.
6. **Predicción separada:** el modelo temporal, la memoria y el motor determinista de seguridad son componentes diferentes. La predicción no cambia por sí sola el nivel de riesgo ni activa una decisión clínica.
7. **Contrato tipado:** toda salida predictiva debe identificar versión del modelo, horizonte temporal, variables disponibles, cobertura de datos, incertidumbre, fecha, estado de calibración y limitaciones.
8. **Privacidad por defecto:** EMA/check-ins y diario explícitamente consentidos son la fuente inicial. No recoger GPS pasivo, teclado, contactos ni contenido de terceros por defecto.
9. **No regresión:** cambios de psychcast no modifican la instancia ni los datos de psychDeep. Migraciones aditivas, pruebas de compatibilidad y despliegues separados.
10. **Sin secretos en Git:** claves Supabase, tokens de Render, credenciales de proveedores LLM y claves de acceso no deben aparecer en código, logs, issues ni archivos .env versionados.

## Arquitectura lógica

```text
Paciente / terapeuta
        │ HTTPS
        ▼
Frontend React/Vite en Render (psychcast.bfab.io)
        │ JWT / HTTPS
        ▼
API FastAPI en Render (servicio independiente)
        ├── autenticación, autorización y consentimiento
        ├── cuatro agentes LLM existentes y su enrutamiento
        ├── memoria longitudinal transversal con procedencia
        ├── analítica longitudinal y características temporales
        ├── motor determinista de seguridad (independiente del LLM)
        ├── interfaz tipada y opcional para predicción
        └── auditoría, versionado y observabilidad
                  │
                  ▼
          Supabase psychcast
          ├── registros clínicos y EMA
          ├── consentimiento / permisos
          ├── memoria derivada y referencias a fuentes
          ├── características y ejecuciones de modelos
          └── auditoría e historial de cambios
```

El cómputo de entrenamiento/inferencia puede incorporarse en una fase posterior (por ejemplo, Modal u otro entorno aprobado). No es requisito para desplegar la app básica y no debe implicar enviar datos clínicos a terceros sin evaluación, contrato, base jurídica, controles de acceso y minimización adecuados.

## Memoria transversal

La memoria se consulta desde todos los agentes mediante una API común con autorización por paciente, terapeuta, ámbito y propósito. Cada elemento debería incluir, como mínimo:

- `memory_id`, `subject_id`, tipo (`episode`, `summary`, `fact`, `relationship`, `hypothesis` o `plan`);
- contenido y referencias a los registros fuente;
- `created_at`, `valid_from`, `valid_until` y estado de revisión;
- procedencia (usuario, profesional, importación o modelo), modelo/versión si aplica;
- consentimiento/permiso aplicado, nivel de sensibilidad y política de retención;
- versión, estado de borrado/rectificación y rastro de auditoría.

La recuperación debe filtrar permisos antes de recuperar o pasar contexto al modelo. El resumen nunca debe ocultar contradicciones, temporalidad o incertidumbre. Las correcciones del usuario/profesional deben poder invalidar o reemplazar una memoria derivada sin borrar el registro original.

## Predicción temporal: estrategia de investigación

No se habilita ninguna predicción clínica en producción por el mero hecho de añadir esta arquitectura. Orden recomendado:

1. Definir resultado, horizonte temporal, unidad de análisis, población, prevención de fuga de datos y plan de evaluación.
2. Validar calidad, frecuencia, faltantes, cambios de instrumentos y sesgos de selección de EMA/check-ins.
3. Establecer una línea base interpretable y calibrada: regresión logística o modelo de supervivencia.
4. Comparar, si hay tamaño y calidad suficientes, GRU-D/GRU con deltas temporales explícitos y máscara de datos faltantes; después, un Transformer temporal compacto.
5. Evaluar BEHRT/Hi-BEHRT solo si escala, vocabulario, licencias y distribución de datos lo justifican.
6. Validación temporal y externa, calibración, sensibilidad, especificidad, PPV/NPV, métricas de utilidad, subgrupos, deriva y análisis de errores.
7. Modo sombra y revisión prospectiva antes de cualquier uso visible o acción automatizada.

Una sola trayectoria individual no basta para entrenar ni validar un predictor general de recaídas. La personalización respecto a la línea base individual puede investigarse, pero no equivale a una probabilidad validada.

## Datos y datasets

Priorizar datos propios recogidos con consentimiento explícito y gobernanza documentada. Datasets públicos de depresión, psicosis, ESM/EMA, GLOBEM, RADAR-MDD, BD², Depresjon o datos sintéticos como Synthea requieren revisión de licencia, acceso, población, variables, protocolo y compatibilidad del resultado objetivo. Ningún dataset se considera automáticamente válido para psychcast.

No subir datos clínicos reales, credenciales ni exportaciones de Supabase a GitHub. No usar datos identificables en servicios externos de entrenamiento. Los conjuntos sintéticos sirven para pruebas técnicas, no para demostrar validez clínica.

## Criterios de aceptación

- La aplicación puede desplegarse con una base de datos nueva y sin leer/escribir en psychDeep.
- Los cuatro agentes continúan disponibles y se prueban mediante pruebas de contrato.
- La memoria está integrada mediante un servicio transversal con autorización y trazabilidad.
- La predicción está desactivada por defecto y aislada de decisiones de seguridad.
- Las migraciones son aditivas, reversibles cuando sea viable y probadas en staging.
- Los datos históricos y las decisiones clínicas conservan fuente, tiempo y versión.
- Consentimiento, exportación, rectificación y borrado se diseñan de acuerdo con la normativa aplicable.
- No se afirma eficacia clínica sin validación y aprobación correspondientes.
