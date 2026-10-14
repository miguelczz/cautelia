// Los textos de la pestana de polizas que dependen de un dato: cada uno con su clave
// literal, para que el chequeo de claves sin consumidor las encuentre.
//
// Los limites, los endosos y las preguntas llegan como identificadores del servidor.
// Uno que esta tabla no conoce no se dibuja con una clave inventada: devuelve
// `undefined` y la pantalla lo omite o muestra el identificador tal cual.

import type { Message } from "../../shared/i18n/translate";

const LIMITES: ReadonlyMap<string, Message> = new Map<string, Message>([
  ["a.bodily_injury_per_person", (t) => t("policies.limit.a_bodily_injury_per_person")],
  ["a.bodily_injury_per_accident", (t) => t("policies.limit.a_bodily_injury_per_accident")],
  ["a.property_damage", (t) => t("policies.limit.a_property_damage")],
  ["b.medical_payments_per_person", (t) => t("policies.limit.b_medical_payments_per_person")],
  ["c.uninsured_per_person", (t) => t("policies.limit.c_uninsured_per_person")],
  ["c.uninsured_per_accident", (t) => t("policies.limit.c_uninsured_per_accident")],
  ["d.collision_deductible", (t) => t("policies.limit.d_collision_deductible")],
  [
    "d.other_than_collision_deductible",
    (t) => t("policies.limit.d_other_than_collision_deductible"),
  ],
]);

const ENDOSOS: ReadonlyMap<string, Message> = new Map<string, Message>([
  ["DEF.FAMILY_MEMBER", (t) => t("policies.endorsement.def_family_member")],
  ["A.EXCL.A.5", (t) => t("policies.endorsement.a_excl_a_5")],
  ["D.EXCL.3", (t) => t("policies.endorsement.d_excl_3")],
  ["C.ARBITRATION", (t) => t("policies.endorsement.c_arbitration")],
  ["F.PERIOD_TERRITORY", (t) => t("policies.endorsement.f_period_territory")],
  ["DEF.COVERED_AUTO", (t) => t("policies.endorsement.def_covered_auto")],
  ["D.EXCL.5", (t) => t("policies.endorsement.d_excl_5")],
  ["D.TRANSPORT", (t) => t("policies.endorsement.d_transport")],
  ["B.INS", (t) => t("policies.endorsement.b_ins")],
  ["F.TERMINATION", (t) => t("policies.endorsement.f_termination")],
]);

const PREGUNTAS: ReadonlyMap<string, Message> = new Map<string, Message>([
  ["hail", (t) => t("policies.question.hail")],
  ["rental_car", (t) => t("policies.question.rental_car")],
  ["theft", (t) => t("policies.question.theft")],
  ["uninsured_driver", (t) => t("policies.question.uninsured_driver")],
  ["lend_car", (t) => t("policies.question.lend_car")],
  ["passengers_medical", (t) => t("policies.question.passengers_medical")],
  ["report_deadline", (t) => t("policies.question.report_deadline")],
  ["abroad", (t) => t("policies.question.abroad")],
  ["towing", (t) => t("policies.question.towing")],
  ["transport_expense_extension", (t) => t("policies.question.transport_expense_extension")],
  ["ride_app_exclusion_reopened", (t) => t("policies.question.ride_app_exclusion_reopened")],
  [
    "temporary_substitute_definition",
    (t) => t("policies.question.temporary_substitute_definition"),
  ],
  ["tire_exclusion_reopened", (t) => t("policies.question.tire_exclusion_reopened")],
  [
    "covered_auto_definition_changed",
    (t) => t("policies.question.covered_auto_definition_changed"),
  ],
]);

/** El orden en que se leen los limites: de la Parte A a la D, como la poliza. */
export const LIMIT_ORDER: readonly string[] = [...LIMITES.keys()];

export function limitLabel(key: string): Message | undefined {
  return LIMITES.get(key);
}

export function endorsementLabel(clauseKey: string): Message | undefined {
  return ENDOSOS.get(clauseKey);
}

export function questionLabel(id: string): Message | undefined {
  return PREGUNTAS.get(id);
}
