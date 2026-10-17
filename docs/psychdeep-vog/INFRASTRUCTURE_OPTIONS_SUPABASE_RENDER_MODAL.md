# Infraestructura propuesta: Supabase, Render y Modal
**Fecha de revisión:** 2026-10-16. Evaluación preliminar, no auditoría contractual completa.

## Decisión recomendada
Mantener **Supabase PostgreSQL como única fuente clínica de verdad** y **Render para frontend/API** durante la remodelación del piloto. Evaluar **Modal solo como cómputo aislado** para experimentos y, si procede, inferencia escalable en una fase posterior. No se recomienda una migración de datos ahora.

## Observaciones confirmadas del entorno
- Supabase project `psychdeep`, ref `ifwexmoltnybvmrsuwtu`, región `eu-north-1`, PostgreSQL 17.6.1.155, estado `ACTIVE_HEALTHY`.
- Esquema `psychdeep_v12`; incluye datos de usuario/consentimiento/asignación, check-ins, diario, observaciones, baselines, señales, ejecuciones de modelos, alertas y memoria.
- Los advisories de Supabase muestran una advertencia de seguridad por extensión `vector` instalada en `public` y múltiples claves foráneas sin índice que las cubra. Son acciones de revisión, no evidencia suficiente para migrar. No se ha modificado el schema.
- Render API `psychdeep-api` y frontend `psychdeep-web` en Frankfurt, vinculados a repo `oibaf88/psychDeep-3`. En la consulta ambos servicios estaban en plan `free`. No se encontró una instancia de Render Postgres en el workspace.
- No se han comparado contratos firmados, retención real de logs, backups efectivos, RPO/RTO ni condiciones de tratamiento de datos de salud de cada proveedor. Deben validarse antes de uso asistencial.

## Matriz de decisión

| Capacidad | Supabase | Render | Modal |
|---|---|---|---|
| Fuente de verdad PostgreSQL | Mejor opción actual: datos ya existentes, constraints/RLS, API y vector | PostgreSQL gestionado posible, pero implicaría migración y compatibilidad a verificar | No es el sistema transaccional adecuado para registro clínico |
| Autorización y APIs | Auth/RLS/roles; mantener políticas y probar permisos | API FastAPI existente; no delegar acceso clínico a endpoints de cómputo | Endpoint de modelo necesita autenticación/autorización upstream |
| Frontend/API | No necesita reemplazar servicios existentes | Ya hospeda la aplicación | No es necesario mover UI/API en primera fase |
| Deep-learning CPU/GPU | Adecuado para datos/consultas y features; GPU de training no es su función principal | Worker/cron útiles para jobs moderados; evaluar memoria/CPU y coste de proceso continuo | Interesante para GPU/CPU bajo demanda, batch e inferencia con carga variable |
| Backup/PITR | Depende del plan contratado y habilitación concreta | PITR y backup de Postgres dependen del plan; free no ofrece el mismo nivel de recuperación | Volúmenes/checkpoints deben tratarse como almacenamiento de cómputo, no como copia maestra |
| Residencia UE | Proyecto actual en eu-north-1; revisar soporte/subprocesadores/transferencias | Servicios actuales en Frankfurt; verificar logs y subprocesadores | Regiones UE disponibles para funciones en modalidades/planes compatibles; verificar ingress/routing y todo tratamiento periférico |
| Coste | Coste de DB, compute, backups/egress y plan | API/frontend con coste según instancias; trabajo intensivo puede elevar cómputo continuo | Pago por segundos puede resultar eficiente para carga GPU variable; añadir carga de modelo, egress, volúmenes, plan/Enterprise y operación |
| Riesgo de continuidad | Mínimo si se mantiene sin cambios | Bajo si no se cambian URLs ni repos de servicio | Añadirlo como servicio no requiere migrar DB y por ello puede ser reversible |

## Opciones de despliegue

### Fase 0 — preservar y medir (ahora)
- No modificar servicios ni DB.
- Confirmar plan de Supabase y política real de backup/PITR. Obtener prueba documentada de recuperación y revisar alertas.
- Revisar los advisory de la extensión vector y los índices ausentes en un entorno de pruebas; producir migración aditiva, medir consultas y plan de rollback antes de aplicar cambios.
- Revisar retención de logs, errores que podrían contener contenido clínico, JWT/RLS, acceso asignado y secretos de Render.
- Establecer objetivos de disponibilidad, recuperación y soporte acorde al piloto.

### Fase 1 — predicción sin migración
- Dataset builder de solo lectura lee de Supabase por API backend con mínimo privilegio.
- Entrenamiento inicial con datos sintéticos/de-identificados o entorno aprobado; resultados en almacén de experimentación aparte.
- Render orquesta API, tareas ligeras y un worker según uso/recursos. No almacenar extractos de texto del paciente en logs ni artefactos sin aprobación.
- El registro clínico sigue capturando la misma información, con los mismos IDs/contratos actuales.

### Fase 2 — Modal solo si benchmarking lo justifica
- Ejecutar entrenamiento batch o inferencia en funciones con región UE validada.
- Enviar identificadores de correlación efímeros/seudónimos y payload mínimo; evitar que Modal consulte directamente tablas clínicas con credenciales privilegiadas.
- Devolver predicción/versiones/metadatos mínimos. Persistir resultado por API de backend autorizada, con consent checks y control de concurrencia.
- Asegurar contrato de tratamiento de datos y subprocesadores, condiciones Enterprise si requeridas, DPA, transferencias, región de entrada y ejecución, logs, volúmenes/snapshots, retención y borrado. No se asume que “región UE” por sí sola cumpla GDPR.
- Calcular coste total con carga del modelo, warm/cold starts, CPU/GPU-segundos, egress, artefactos, logs y cuota de disponibilidad.

### Fase 3 — evaluar DB alternativa solo por evidencia
Considerar Render Postgres u otra solución solo si se documenta una necesidad concreta (coste total, rendimiento p95, disponibilidad, control operativo, contractual o interoperabilidad) y hay:
1. backup restaurado de ensayo;
2. migración/replicación probada sin interrumpir ingesta;
3. comparación de row counts, IDs, relaciones, time ranges y checksums;
4. dual-read/control de discrepancias;
5. ventana de corte y rollback aprobada;
6. demostración de que check-ins/diario/consentimientos y registros de seguimiento continúan sin pérdida.
Nunca hacer de la tabla clínica una copia temporal sin controles o cambiar la URL de producción antes de aprobar esta puerta.

## Fuentes oficiales consultadas
- Supabase capacidades: https://supabase.com/docs/guides/getting-started/features
- Supabase backups: https://supabase.com/features/database-backups
- Supabase pricing y backup/PITR por plan: https://supabase.com/pricing
- Render PostgreSQL y backups: https://render.com/docs/postgresql y https://render.com/docs/postgresql-backups
- Modal pricing/security/DPA/region selection: https://modal.com/pricing, https://modal.com/docs/guide/security, https://modal.com/legal/dpa, https://modal.com/blog/region-selection-launch
