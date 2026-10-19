# Matriz finalidad → art. 6 + art. 9 → retención → encargado

**Estado:** instrumento de trabajo interno. **No** es una EIPD cerrada, **no** es un registro de actividades (art. 30 RGPD) completo y **no** afirma conformidad, marcado CE ni autorización AEMPS.

**Fuentes vinculantes:** Reglamento (UE) 2016/679 (RGPD); Ley Orgánica 3/2018 (LOPDGDD); Ley 41/2002; Ley 14/2007; Reglamento (UE) 2017/745 (MDR).  
**Guía (no vinculante):** AEPD, guía sector sanitario y FAQs de datos de salud; MDCG 2019-11.  
**Hecho de producto (Asis, 2026-10-18):** PsychDeep es autorregulación longitudinal, no investigación y no chatbot clínico. La seguridad determinista es independiente del LLM.

**Incertidumbre abierta:** identidad jurídica del responsable; DPD; contratos de encargado (Supabase, Render, Anthropic u otros LLM); si el tratamiento es «asistencia sanitaria» art. 9.2.h (profesional con secreto) o producto digital con 9.2.a; si el diario constituye historia clínica Ley 41/2002 art. 17.

## Neuroimagen (finalidad distinta)

`data_processing` no cubre DICOM/NIfTI. `require_imaging_grant` va antes de `write_imaging_change`. El writer se niega sin grant, con menos de dos volúmenes comparables de la misma familia de secuencia, o sin protocolo humano de hallazgo incidental. No hay tabla. No escribe `alert_level`. No se recaba el grant hasta que exista ingestión versionada.

El resto de la matriz de `master` no se reescribe aquí. La fila de neuroimagen es la única adición de esta rama respecto del texto ya mergeado.
