import { describe, expect, it } from "vitest";
import { readComparison } from "../longitudinalModel";
import { suggestedActionFromReading } from "../hoySuggestedAction";
import {
  calculatedLongitudinal,
  insufficientLongitudinal,
  stableLongitudinal,
} from "./longitudinalFixtures";

const formDefaults = { craving: 3, self_efficacy: 5 };

describe("suggestedActionFromReading", () => {
  it("suggests Regular when craving is higher / mood lower in calculated longitudinal", () => {
    const reading = readComparison(calculatedLongitudinal, "patient");
    const action = suggestedActionFromReading(reading, formDefaults);
    expect(action.actionId).toBe("hoy.suggest.regular_wave");
    expect(action.driver).toBe("longitudinal_adverse");
    expect(action.route).toBe("/wave");
    expect(action.button).toBe("Ir a Regular");
    expect(action.title).toMatch(/Regular/i);
    expect(action.body).not.toMatch(/sin riesgo|todo va bien|todo vaya bien/i);
  });

  it("suggests Tendencias for a stable-only calculated reading", () => {
    const reading = readComparison(stableLongitudinal, "patient");
    const action = suggestedActionFromReading(reading, formDefaults);
    expect(action.actionId).toBe("hoy.suggest.trends_explain");
    expect(action.driver).toBe("calculated_explain");
    expect(action.route).toBe("/trends");
    expect(action.button).toBe("Ver Tendencias");
    expect(action.title).toMatch(/explicación|cambio/i);
    expect(action.body).toMatch(/Tendencias|comparación/i);
    expect(action.body).not.toMatch(/sin riesgo/i);
    expect(action.body).toMatch(/no.*nivel de alerta|sin interpretarlo como un nivel de alerta/i);
  });

  it("keeps a soft Tendencias option when reference is insufficient (never claims fine)", () => {
    const reading = readComparison(insufficientLongitudinal, "patient");
    const action = suggestedActionFromReading(reading, formDefaults);
    expect(action.actionId).toBe("hoy.suggest.register_observe");
    expect(action.driver).toBe("insufficient_observe");
    expect(action.route).toBe("/trends");
    expect(action.button).toBe("Ver Tendencias");
    expect(action.title).toBe("Registrar y observar");
    expect(action.body).toMatch(/no significa que todo vaya bien|ni que no haya riesgo/i);
    expect(action.body).not.toMatch(/sin riesgo|todo está bien/i);
  });

  it("prefers Regular when the in-progress form is acutely high craving", () => {
    const reading = readComparison(stableLongitudinal, "patient");
    const action = suggestedActionFromReading(reading, { craving: 8, self_efficacy: 5 });
    expect(action.actionId).toBe("hoy.suggest.regular_wave");
    expect(action.driver).toBe("acute_craving");
    expect(action.route).toBe("/wave");
    expect(action.button).toBe("Ir a Regular");
    expect(action.title).toBe("Regular una ola");
  });

  it("prefers Regular when the in-progress form has very low self-efficacy", () => {
    const reading = readComparison(stableLongitudinal, "patient");
    const action = suggestedActionFromReading(reading, { craving: 3, self_efficacy: 2 });
    expect(action.actionId).toBe("hoy.suggest.regular_wave");
    expect(action.driver).toBe("acute_self_efficacy");
    expect(action.route).toBe("/wave");
    expect(action.button).toBe("Ir a Regular");
    expect(action.title).toBe("Bajar el ritmo");
  });

  it("never reads alert level into the action (null reading stays soft)", () => {
    const action = suggestedActionFromReading(null, formDefaults);
    expect(action.actionId).toBe("hoy.suggest.register_observe");
    expect(action.route).toBe("/trends");
    expect(action.button).toBe("Ver Tendencias");
    expect(JSON.stringify(action)).not.toMatch(/alert|Nivel|risk/i);
  });
});
