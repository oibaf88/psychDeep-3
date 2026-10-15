## 2024-11-20 - Missing Accessibility and UX Form Input Labels
**Learning:** Found that basic text and password inputs in this app often lacked explicit `htmlFor` bindings and visual required indications `*` despite using the HTML5 `required` attribute.
**Action:** Always verify that inputs are correctly bound to labels using `htmlFor` and `id`, and provide a visual required indicator on labels for required fields to improve basic form usability.

## 2024-11-20 - Missing Accessibility Labels for Standalone Inputs
**Learning:** Found that standalone chat inputs and copilot prompts lacked associated visible labels or `aria-label` attributes, hindering screen reader accessibility.
**Action:** Add `aria-label` directly to inputs where visual labels would clutter the UI (like chat bars or copilot prompts) to ensure keyboard/screen-reader users understand their purpose.
## 2026-10-07 - Botones de adjudicación con contexto
**Learning:** En listas o tarjetas múltiples (como DomainCard) que repiten botones de acción ('Confirmar', 'Refutar'), los usuarios de lectores de pantalla pierden el contexto si no hay `aria-label` específicos que conecten la acción con el ítem concreto.
**Action:** Usar `aria-label` dinámicos que incluyan el título de la tarjeta o el elemento afectado, incluso en aplicaciones clínicas complejas.
## 2026-10-07 - Botones de adjudicación con contexto
**Learning:** En listas o tarjetas múltiples (como DomainCard o listas de alertas) que repiten botones de acción ('Confirmar', 'Refutar', 'Resolver', 'Descartar') y campos de texto (como notas de resolución), los usuarios de lectores de pantalla pierden el contexto si no hay `aria-label` específicos que conecten la acción con el ítem concreto.
**Action:** Usar `aria-label` dinámicos que incluyan el título de la tarjeta o el elemento afectado (ej. `aria-label={"Resolver alerta " + a.title}`) en todos los botones de acción y campos de texto interactivos dentro de listas iteradas, asegurando el contexto en aplicaciones clínicas complejas.
