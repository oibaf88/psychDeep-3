# Mobile Setup — PsychDeep local inference

## Objetivo
PsychDeep soportará cuatro modos de inferencia independientes:
1. mobile-local — inferencia directamente en Android, sin Cloudflare Tunnel.
2. local-tunnel — LM Studio/Ollama/etc. en Windows/macOS/Linux, accesible desde Render mediante HTTPS autenticado.
3. commercial-approved — Anthropic, manteniendo la integración existente.
4. cloud-tuned — endpoint compatible con OpenAI gestionado en la nube, si se habilita.

No existe fallback automático entre proveedores. El modo se selecciona explícitamente y cada ejecución queda identificada por su deployment alias.

## Arquitectura móvil
Android / PsychDeep
  → UI web/native
  → Native Mobile AI bridge
  → llama.cpp o MLC LLM
  → modelo local
  → almacenamiento local SQLite
  → HTTPS outbound
  → Render API y/o Supabase Edge Function

El teléfono nunca necesita aceptar conexiones entrantes. Por tanto, mobile-local no utiliza Cloudflare Tunnel. El flujo es outbound-only.

## Nuevo deployment: mobile-local
Debe añadirse un alias mobile-local separado de local-tunnel.

local-tunnel significa: Render → HTTPS → ordenador del usuario → LM Studio.
mobile-local significa: Android → modelo local → resultado → HTTPS → backend.

No se debe reutilizar MODEL_LOCAL_BASE_URL para mobile-local, porque ese ajuste describe un endpoint que el backend puede contactar.

## MobileInferenceEvent
El teléfono genera un evento de inferencia que el backend puede validar y registrar:

{
  "event_id": "uuid",
  "conversation_id": "uuid",
  "model_run_id": "uuid",
  "deployment_alias": "mobile-local",
  "model_id": "modelo-local",
  "model_version": "version",
  "prompt_version": "version",
  "input_hash": "sha256",
  "output": {},
  "client_timestamp": "timestamp",
  "idempotency_key": "uuid"
}

El servidor valida esquema, identidad, versión, permisos e idempotencia antes de incorporar el resultado.

## Persistencia local y sincronización
El móvil mantiene una cola local:
PENDING → UPLOADING → SYNCED

Sin conexión:
chat → inferencia local → SQLite → pending_sync

Con conexión:
SQLite → HTTPS → backend → ACK → synced

Estados recomendados: local_only, pending_sync, synced, sync_failed y conflict.

Los datos locales no deben borrarse automáticamente al recibir un ACK; la política de retención será explícita.

## Cambios previstos en backend
model_gateway.py debe conservar LOCAL_TUNNEL, CLOUD_TUNED y COMMERCIAL_APPROVED y añadir MOBILE_LOCAL.

mobile-local no debe pasar por OpenAICompatibleProvider como si el servidor pudiera contactar con el teléfono. Necesita un adaptador de ingestión de resultados móviles.

model_deployments debe registrar mobile-local con adapter mobile_local y status aprobado.

model_runs debe conservar deployment alias, model_id, model_version, prompt_version, input_hash, output_schema, correlation_id, latencia y estado. Conviene añadir metadatos de cliente: client_platform, client_app_version, client_model_checksum e inference_engine.

## Android
Para el primer prototipo recomiendo llama.cpp. Su documentación oficial incluye integración Android, carga de modelos GGUF desde almacenamiento privado y ejecución local. citeturn0search0

MLC LLM es una alternativa si interesa un runtime móvil con API compatible con OpenAI. citeturn0search2turn0search12

No fijar todavía un modelo concreto en código. Crear un ModelRegistry con model_id, formato, cuantización, SHA-256, contexto, memoria mínima y capacidades.

El checksum del modelo debe verificarse antes de activarlo.

## Setup de desarrollo
Instalar Android Studio, Android SDK, NDK, CMake y un JDK compatible. llama.cpp documenta tanto Android Studio como compilación mediante Android NDK. citeturn0search0

Estructura propuesta:
mobile/
  android/
  ai/
    LocalInferenceEngine
    ModelRegistry
    PromptAdapter
  storage/
    LocalDatabase
    SyncQueue
  sync/
    SyncClient
    SyncWorker

Primer objetivo: Android → LocalInferenceEngine → respuesta → SQLite, completamente offline.

Segundo objetivo: SQLite → SyncClient → HTTPS → Render API → PostgreSQL/Supabase.

La sincronización no depende de que el modelo continúe disponible.

## Seguridad
No almacenar en APK ni en almacenamiento accesible por el navegador claves de Anthropic, service_role, secretos de Render, tokens Cloudflare ni credenciales de LM Studio.

El almacenamiento local que contenga datos clínicos debe estar protegido con almacenamiento privado de Android y cifrado cuando corresponda.

Para Supabase, las Edge Functions pueden interponer lógica autenticada entre cliente y Postgres; la documentación actual describe validación JWT, políticas y secretos del lado servidor. citeturn0search1turn0search11

## Compatibilidad con las opciones existentes
La web puede seguir utilizando Anthropic, local-tunnel y cloud-tuned.

En Android el selector puede mostrar:
- En este dispositivo → mobile-local
- Servidor local del PC → local-tunnel
- Anthropic → commercial-approved
- Cloud → cloud-tuned

No hay fallback silencioso entre ellos.

## RAG: qué es
RAG significa Retrieval-Augmented Generation. El sistema primero recupera información relevante y después la proporciona al LLM como contexto:
pregunta → retrieval → contexto → LLM → respuesta

El retrieval puede usar búsqueda textual, embeddings/vector search o una combinación híbrida.

## Qué hay ahora en PsychDeep
El repositorio ya tiene psychdeep_v12.knowledge_items con topic, population, locale, evidence_level, contraindications, content, content_version, review_due, source_ref, approved_by y status.

Eso es un registro de conocimiento curado, no un RAG operativo.

El propio repositorio marca RAG de contenidos como NOT STARTED. La búsqueda del código revisado no encontró embeddings, pgvector ni un pipeline de retrieval implementado.

## Qué aportaría un RAG real
KnowledgeItem → versionado → chunking → embedding → índice vectorial → retrieval → filtros/reranking → contexto autorizado → LLM.

Ventajas:
1. Respuestas ancladas en fuentes concretas.
2. Proveniencia por fragmento.
3. Actualización del conocimiento sin reentrenar el modelo.
4. Filtrado por población, idioma, evidencia y estado.
5. Retirada controlada de versiones antiguas.
6. Evaluación independiente del retrieval y de la generación.

RAG no garantiza corrección. Puede recuperar documentos incorrectos, antiguos o fuera de contexto. Retrieval no debe convertirse en el motor de seguridad ni en el mecanismo que calcula riesgo.

## RAG móvil
No recomiendo duplicar inicialmente todo el índice RAG en Android.

Primera versión: mobile-local LLM + conversación local + RAG cloud opcional.

Más adelante puede existir un RAG local reducido con contenido revisado y versionado para funcionar offline. El índice local debería ser una caché versionada y verificable, no un corpus clínico modificable por el cliente.

## Roadmap
Fase 1 — Mobile inference
- Android bridge
- llama.cpp
- ModelRegistry
- LocalInferenceEngine
- SQLite
- offline chat
- checksum
- metadatos de modelo

Fase 2 — Mobile sync
- MobileInferenceEvent
- endpoint de ingestión
- idempotencia
- SyncQueue
- retry/backoff
- ACK
- model_run audit
- RLS/auth

Fase 3 — Hybrid routing
- mobile-local
- local-tunnel
- Anthropic
- cloud-tuned
- selector explícito
- tests de aislamiento
- sin fallback silencioso

Fase 4 — RAG
- gobernanza de KnowledgeItem
- chunking/versioning
- embeddings
- vector index
- retrieval híbrido
- filtros de población/locale/evidencia
- provenance
- retrieval evaluation
- generación con contexto

Fase 5 — Local RAG
- corpus clínico reducido
- índice local versionado
- actualización firmada
- checksum
- rollback de corpus
- modo offline completo

## Resultado arquitectónico
PsychDeep pasa de un único camino local basado en túnel a una frontera de inferencia con cuatro adaptadores:
mobile-local | local-tunnel | cloud-tuned | commercial-approved

El modelo deja de definir el transporte. La aplicación define el modo de inferencia y cada modo tiene su propio adaptador, auditoría y política de datos.