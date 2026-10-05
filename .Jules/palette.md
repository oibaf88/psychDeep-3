## 2024-11-20 - Missing Accessibility and UX Form Input Labels
**Learning:** Found that basic text and password inputs in this app often lacked explicit `htmlFor` bindings and visual required indications `*` despite using the HTML5 `required` attribute.
**Action:** Always verify that inputs are correctly bound to labels using `htmlFor` and `id`, and provide a visual required indicator on labels for required fields to improve basic form usability.

## 2024-11-20 - Missing Accessibility Labels for Standalone Inputs
**Learning:** Found that standalone chat inputs and copilot prompts lacked associated visible labels or `aria-label` attributes, hindering screen reader accessibility.
**Action:** Add `aria-label` directly to inputs where visual labels would clutter the UI (like chat bars or copilot prompts) to ensure keyboard/screen-reader users understand their purpose.
