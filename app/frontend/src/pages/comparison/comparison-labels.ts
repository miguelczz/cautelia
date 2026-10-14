// Los textos de la comparacion que dependen de un dato cerrado, cada uno con su
// clave literal dentro de un `switch` exhaustivo (la forma de `metrics-labels.ts`).

import type { Locale } from "../../shared/copy/copy-keys";
import type { Message } from "../../shared/i18n/translate";
import type { ColumnState } from "./comparison-state";

/**
 * Lo que la columna dice de si misma, para quien no ve el color. Una columna sin
 * pregunta (`idle`) no lleva etiqueta: su texto ya dice que espera.
 */
export function stateName(state: Exclude<ColumnState, "idle">): Message {
  switch (state) {
    case "loading":
      return (t) => t("comparison.state.loading");
    case "answered":
      return (t) => t("comparison.state.answered");
    case "failed":
      return (t) => t("comparison.state.failed");
    case "interrupted":
      return (t) => t("comparison.state.interrupted");
    case "rejected":
      return (t) => t("comparison.state.rejected");
  }
}

/**
 * Las preguntas que se ofrecen para cargar en el cuadro. Todas son de cobertura, y
 * una prueba del servidor comprueba que su filtro las admite en los dos idiomas.
 */
export function exampleQuestions(): readonly Message[] {
  return [
    (t) => t("comparison.examples.rental_car"),
    (t) => t("comparison.examples.hail"),
    (t) => t("comparison.examples.uninsured_driver"),
    (t) => t("comparison.examples.stolen_keys"),
    (t) => t("comparison.examples.ride_app"),
    (t) => t("comparison.examples.blown_tire"),
    (t) => t("comparison.examples.passenger_medical"),
    (t) => t("comparison.examples.lend_car"),
  ];
}

/**
 * Cuando se hizo la pregunta, con la hora del dispositivo y en el idioma de la
 * pantalla. Lo guardado dura un dia, asi que basta la hora si es de hoy y se agrega
 * el dia si no. Es un formato y no una frase: no sale del catalogo.
 */
export function askedAtLabel(askedAt: number, now: number, locale: Locale): string {
  const mismoDia = new Date(askedAt).toDateString() === new Date(now).toDateString();
  return new Intl.DateTimeFormat(
    locale,
    mismoDia ? { timeStyle: "short" } : { dateStyle: "medium", timeStyle: "short" },
  ).format(askedAt);
}
