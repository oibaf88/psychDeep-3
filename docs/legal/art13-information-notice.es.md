# Información previa (art. 13 RGPD) — borrador para el registro

**Estado:** texto de producto. **No** sustituye la política de privacidad firmada ni identifica aún al responsable con NIF/domicilio. Hasta que la organización complete los corchetes, el alta **no** puede presentarse como «información completa art. 13».

Este aviso es **de datos** (RGPD). Es distinto del consentimiento informado **sanitario** de la Ley 41/2002. PsychDeep, en la finalidad clínica actual, es autorregulación longitudinal: no diagnostica y el motor de riesgo es determinista, independiente del modelo de lenguaje.

## 1. Responsable

- Identidad: **[pendiente: razón social, NIF, domicilio]**
- Contacto: **[pendiente]**
- Delegado de protección de datos, si existe: **[pendiente / no designado]**

## 2. Finalidades y bases

Los datos de salud (diario, check-in, chat, señales, riesgo) son **categoría especial** (art. 9.1 RGPD). Cada finalidad tiene base en art. 6 **y** excepción en art. 9.2. Detalle: `docs/legal/purpose-legal-basis-matrix.md`.

| Finalidad | ¿Se ofrece ahora? | Base prevista |
|---|---|---|
| Crear la cuenta (email, contraseña, nombre) | sí | art. 6.1.b |
| Núcleo de autorregulación (`data_processing`) | sí, **opt-in explícito** en el alta | arts. 6.1.a y 9.2.a (salvo que conste 9.2.h) |
| Análisis lingüístico/psicosocial del texto (`linguistic_analysis`) | sí, opt-in **aparte** en Consentimientos | arts. 6.1.a y 9.2.a |
| Compartir con un profesional vinculado (`professional_sharing`) | sí, al aceptar la vinculación | arts. 6.1.a y 9.2.a; el acceso debe seguir la vinculación activa |
| SMS de crisis | **no** | no se recaba |
| Investigación, entrenamiento de modelos, embeddings de memoria | **no** | Ley 14/2007 + art. 9.2.j solo con protocolo futuro |

Sin la casilla del núcleo **no** se crea el tratamiento clínico. Revocar una finalidad detiene **nuevas** operaciones de esa finalidad; el histórico puede conservarse por seguridad, auditoría o deber legal (art. 17.3).

## 3. Destinatarios

- Infraestructura de datos y API (encargados: **[Supabase / Render — DPA y región pendientes de constancia]**).
- El modelo de lenguaje **solo** si concedes `linguistic_analysis` (**[proveedor y región pendientes]**). No hay cambio automático de proveedor.
- Profesionales **solo** con vinculación que tú aceptas.
- No se vende el dato. No hay Data API de paciente en el diseño; si el proyecto la tiene instalada, es un control de seguridad, no un destinatario previsto.

## 4. Transferencias fuera del EEE

Solo si un encargado está fuera y hay mecanismo del cap. V (DPA + cláusulas tipo u otra). **[pendiente de verificar por proveedor].** Una región «EU» en el panel no basta.

## 5. Conservación

Mientras la cuenta y el consentimiento de esa finalidad estén vigentes, salvo plazo legal más largo. No está decidido si el diario es historia clínica (Ley 41/2002 art. 17).

## 6. Derechos

Acceso, rectificación, supresión, limitación, portabilidad, oposición, retirar el consentimiento (art. 7.3) y reclamación ante la AEPD (https://www.aepd.es). Hoy la app cubre de forma incompleta exportación y supresión: hay que ejercerlos también ante el responsable.

## 7. Decisiones y perfiles

Hay evaluación de riesgo **determinista** y, si lo consientes, análisis de texto por modelo. El modelo **no** fija el nivel de alerta ni contacta a terceros. Puedes usar check-in, diario y recursos de crisis sin análisis de texto.

## Casilla de alta (copy)

> He leído la información sobre el tratamiento. Consiento de forma **explícita** (arts. 7 y 9.2.a RGPD) que PsychDeep trate mis datos de salud para la autorregulación longitudinal (check-ins, diario, trayectoria, baseline y seguridad determinista). Entiendo que el análisis de mi texto por un modelo es **optativo** y se activa aparte. No autorizo investigación ni entrenamiento de modelos.
