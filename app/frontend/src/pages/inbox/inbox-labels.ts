// Lo que la bandeja lee de un valor cerrado: su etiqueta del catalogo.
//
// **Ninguna pantalla imprime el valor interno de un estado, una resolucion, un
// tipo de registro, un motivo de derivacion, un canal o un campo.**
// `awaiting_insured` no es texto para una persona. Del lado del servidor eso lo
// sostiene `case_record/labels.py`; de este lado, estas tablas.
//
// Son `switch` exhaustivos y no objetos indexados por el valor: el compilador exige
// todos los casos, asi que un valor nuevo del esquema falla aqui en vez de salir
// vacio en pantalla. Donde el valor llega como cadena --la salida de una respuesta
// de cobertura, la clave de etiqueta de un campo-- hay tabla con **rama por
// defecto**, igual que en `problems.ts`: lo que esta version no conoce se dice de
// alguna manera, nunca como un hueco.

import type {
  CaseDetailOut,
  CaseState,
  Channel,
  InboxAction,
  Priority,
  RecordType,
} from "../../shared/api-client/inbox";
import type { CopyKey } from "../../shared/copy/copy-keys";
import type { Message } from "../../shared/i18n/translate";

/**
 * Los dos estados en los que la agente todavia trabaja el caso (verifica la poliza, evalua
 * las reglas): duran unos segundos y un proceso reiniciado los deja atascados. Nadie ha
 * decidido nada ni el caso esta con un ajustador.
 */
export function isUnderReview(state: CaseState): boolean {
  return state === "verifying" || state === "deciding";
}

/**
 * Si el caso lo cerraron las reglas sin que nadie decida (cierre directo, US1.17): cerrado,
 * resolucion `registered` y el sistema como autor de la ultima transicion. Las tres a la
 * vez: `registered` solo no basta, y un actor `system` solo tampoco (los casos de ejemplo
 * que se sembraron antes del 2026-10-13 cerraron todos con el sistema, tambien los que en
 * vivo solo cierra el personal).
 */
export function isClosedByRules(detail: CaseDetailOut): boolean {
  return (
    detail.state === "closed" &&
    detail.resolution === "registered" &&
    detail.explanation.decided_by_kind === "system"
  );
}

/**
 * Lo que dice quien abre su caso mientras la agente lo evalua, en una linea: la que ya
 * usa la pagina de casos. No dice que este con un ajustador, porque todavia no lo esta.
 * Sin frase (`undefined`) en cualquier otro estado.
 */
export function reviewHint(state: CaseState): Message | undefined {
  switch (state) {
    case "verifying":
      return (t) => t("cases.group.verifying");
    case "deciding":
      return (t) => t("cases.group.deciding");
    default:
      return undefined;
  }
}

export function stateLabel(state: CaseState): Message {
  switch (state) {
    case "open":
      return (t) => t("case.state.open");
    case "capturing":
      return (t) => t("case.state.capturing");
    case "verifying":
      return (t) => t("case.state.verifying");
    case "deciding":
      return (t) => t("case.state.deciding");
    case "derived":
      return (t) => t("case.state.derived");
    case "awaiting_insured":
      return (t) => t("case.state.awaiting_insured");
    case "closed":
      return (t) => t("case.state.closed");
  }
}

export function recordTypeLabel(kind: RecordType): Message {
  switch (kind) {
    case "claim":
      return (t) => t("case.record_type.claim");
    case "coverage_inquiry":
      return (t) => t("case.record_type.coverage_inquiry");
    case "quote_request":
      return (t) => t("case.record_type.quote_request");
  }
}

export function channelLabel(channel: Channel): Message {
  switch (channel) {
    case "voice":
      return (t) => t("case.channel.voice");
    case "chat":
      return (t) => t("case.channel.chat");
  }
}

export function priorityLabel(priority: Priority): Message {
  switch (priority) {
    case "high":
      return (t) => t("inbox.priority.high");
    case "normal":
      return (t) => t("inbox.priority.normal");
  }
}

export function actionLabel(action: InboxAction): Message {
  switch (action) {
    case "approve":
      return (t) => t("inbox.decision.approve");
    case "reject":
      return (t) => t("inbox.decision.reject");
    case "mark_sent":
      return (t) => t("inbox.decision.mark_sent");
  }
}

/** Las cuatro resoluciones de U4. Llega como cadena, asi que lleva rama por defecto. */
const RESOLUCIONES: Partial<Record<string, Message>> = {
  registered: (t) => t("case.resolution.registered"),
  approved: (t) => t("case.resolution.approved"),
  rejected: (t) => t("case.resolution.rejected"),
  sent_to_insurer: (t) => t("case.resolution.sent_to_insurer"),
};

export function resolutionLabel(resolution: string): Message {
  return RESOLUCIONES[resolution] ?? ((t) => t("case.field_unavailable"));
}

/** Los tres motivos de derivacion. `null` dice que no hay, y lo dice con palabras. */
const MOTIVOS: Partial<Record<string, Message>> = {
  demo_limit: (t) => t("case.derivation_reason.demo_limit"),
  person_requested: (t) => t("case.derivation_reason.person_requested"),
  rule: (t) => t("case.derivation_reason.rule"),
};

export function derivationReasonLabel(reason: string | null): Message {
  if (reason === null) {
    return (t) => t("inbox.case.no_reason");
  }
  return MOTIVOS[reason] ?? ((t) => t("inbox.case.no_reason"));
}

/**
 * Lo que dice el renglon «Por que llego aqui» de un caso (2026-10-13).
 *
 * El motivo de derivacion, cuando lo hay. Cuando no lo hay, «sin motivo registrado» solo
 * tiene sentido para un caso que si pudo haber llegado a alguien y no dejo la razon; en
 * los dos que nunca llegaron a un ajustador se leia como un dato que faltaba, justo al lado
 * de «sin ajustador: lo cerraron las reglas»:
 *
 * - **lo cerraron las reglas**: no paso por un ajustador;
 * - **la agente aun lo evalua** (`verifying`, `deciding`): la frase de siempre para eso.
 *
 * Los demas estados dicen lo que decian.
 */
export function caseReasonLabel(detail: CaseDetailOut): Message {
  if (detail.derivation_reason !== null) {
    return derivationReasonLabel(detail.derivation_reason);
  }
  if (isClosedByRules(detail)) {
    return (t) => t("inbox.case.not_handed_off");
  }
  return reviewHint(detail.state) ?? derivationReasonLabel(null);
}

/**
 * Las cuatro salidas de una respuesta de cobertura (BR2.5).
 *
 * **Cuatro entradas y cuatro frases distintas.** "Sin clausula" y "no pude
 * verificar" son dos valores distintos en el estado, en la traza y en el reporte de
 * evaluaciones, y lo son tambien aqui: colapsarlos contaminaria con fallos de
 * infraestructura una respuesta que si se verifico. Que las cuatro frases difieran
 * de verdad lo mide el caso de golden set de esta unidad, sobre el catalogo.
 */
const COBERTURA: Partial<Record<string, Message>> = {
  verified: (t) => t("inbox.coverage.verified"),
  rejected: (t) => t("inbox.coverage.rejected"),
  no_clause_found: (t) => t("inbox.coverage.no_clause_found"),
  unverifiable: (t) => t("inbox.coverage.unverifiable"),
};

export function coverageOutcomeLabel(outcome: string): Message {
  return COBERTURA[outcome] ?? ((t) => t("case.field_unavailable"));
}

/**
 * La etiqueta de un campo del caso, por la clave que manda el servidor.
 *
 * La clave viene del cable porque el juego de campos lo declara el esquema de U4 y
 * su correspondencia con el catalogo vive alli, con su prueba en los dos sentidos.
 * Aqui solo se resuelve, con la clave escrita literal: `t()` la exige asi, y una
 * clave armada en ejecucion no aparece en el chequeo de claves sin consumidor.
 */
const CAMPOS: Partial<Record<CopyKey, Message>> = {
  "case.field.identity_and_policy": (t) => t("case.field.identity_and_policy"),
  "case.field.incident_datetime": (t) => t("case.field.incident_datetime"),
  "case.field.location": (t) => t("case.field.location"),
  "case.field.description": (t) => t("case.field.description"),
  "case.field.vehicle_and_driver": (t) => t("case.field.vehicle_and_driver"),
  "case.field.other_parties": (t) => t("case.field.other_parties"),
  "case.field.injuries": (t) => t("case.field.injuries"),
  "case.field.question_asked": (t) => t("case.field.question_asked"),
  // La solicitud de cotizacion (U19): sus diecisiete campos, uno por clave del esquema.
  "case.field.driver_name": (t) => t("case.field.driver_name"),
  "case.field.driver_birth_date": (t) => t("case.field.driver_birth_date"),
  "case.field.license_years": (t) => t("case.field.license_years"),
  "case.field.license_jurisdiction": (t) => t("case.field.license_jurisdiction"),
  "case.field.vehicle_year": (t) => t("case.field.vehicle_year"),
  "case.field.vehicle_make": (t) => t("case.field.vehicle_make"),
  "case.field.vehicle_model": (t) => t("case.field.vehicle_model"),
  "case.field.vin": (t) => t("case.field.vin"),
  "case.field.salvage_title": (t) => t("case.field.salvage_title"),
  "case.field.vehicle_age_years": (t) => t("case.field.vehicle_age_years"),
  "case.field.use_type": (t) => t("case.field.use_type"),
  "case.field.annual_mileage_band": (t) => t("case.field.annual_mileage_band"),
  "case.field.garaging_jurisdiction": (t) => t("case.field.garaging_jurisdiction"),
  "case.field.at_fault_losses_3y": (t) => t("case.field.at_fault_losses_3y"),
  "case.field.claims_3y": (t) => t("case.field.claims_3y"),
  "case.field.prior_coverage_active": (t) => t("case.field.prior_coverage_active"),
  "case.field.lapse_months": (t) => t("case.field.lapse_months"),
  "case.field_unavailable": (t) => t("case.field_unavailable"),
};

export function fieldLabel(labelKey: string): Message {
  return CAMPOS[labelKey as CopyKey] ?? ((t) => t("case.field_unavailable"));
}

/** Las claves de campo que esta version sabe decir. La usa su prueba para no copiarlas. */
export const KNOWN_FIELD_LABEL_KEYS = Object.keys(CAMPOS) as readonly CopyKey[];

const UN_MINUTO = 60_000;
const UNA_HORA = 60 * UN_MINUTO;
const UN_DIA = 24 * UNA_HORA;

/**
 * Cuanto lleva esperando un caso, en la unidad que se lee de un vistazo (BR1.2).
 *
 * La espera se calcula en la pantalla y no en el servidor **a proposito**: un texto
 * como "hace 4 min" calculado al servir queda mintiendo en cuanto pasa un minuto, y
 * la pestana de la bandeja se queda abierta. Lo que el servidor manda es el
 * instante, que no caduca.
 */
export function waitedLabel(since: string, now: Date): Message {
  const desde = new Date(since).getTime();
  const transcurrido = Math.max(now.getTime() - desde, 0);
  if (Number.isNaN(desde) || transcurrido < UN_MINUTO) {
    return (t) => t("inbox.waited.just_now");
  }
  if (transcurrido < UNA_HORA) {
    const minutos = Math.floor(transcurrido / UN_MINUTO);
    return (t) => t("inbox.waited.minutes", { value: minutos });
  }
  if (transcurrido < UN_DIA) {
    const horas = Math.floor(transcurrido / UNA_HORA);
    return (t) => t("inbox.waited.hours", { value: horas });
  }
  const dias = Math.floor(transcurrido / UN_DIA);
  return (t) => t("inbox.waited.days", { value: dias });
}

/**
 * El titulo de "Ver mi caso": lo que es el caso, en palabras, y no su codigo (C10,
 * 2026-10-12). El codigo va aparte, en un renglon pequeno que dice para que sirve.
 */
export function ownCaseTitle(kind: RecordType): Message {
  switch (kind) {
    case "claim":
      return (t) => t("visitor.title_claim");
    case "coverage_inquiry":
      return (t) => t("visitor.title_inquiry");
    case "quote_request":
      return (t) => t("visitor.title_quote");
  }
}

/**
 * Por que las reglas dejaron el caso como lo dejaron, en una frase (E3, 2026-10-12).
 *
 * La categoria llega como cadena, asi que lleva rama por defecto: una categoria que
 * esta version no conoce se dice con una frase general y no se imprime.
 */
export function ruleReasonLabel(category: string): Message {
  switch (category) {
    case "referral":
      return (t) => t("inbox.rule.reason.referral");
    case "standard_review":
      return (t) => t("inbox.rule.reason.standard_review");
    case "direct_close":
      return (t) => t("inbox.rule.reason.direct_close");
    default:
      return (t) => t("inbox.rule.reason.other");
  }
}

/**
 * La categoria de las reglas en una o dos palabras, para la etiqueta del encabezado
 * (2026-10-13). Llega como cadena, asi que lleva rama por defecto: una categoria que esta
 * version no conoce se dice como «otra» y nunca se imprime el valor.
 */
export function ruleCategoryLabel(category: string): Message {
  switch (category) {
    case "referral":
      return (t) => t("inbox.rule.category.referral");
    case "standard_review":
      return (t) => t("inbox.rule.category.standard_review");
    case "direct_close":
      return (t) => t("inbox.rule.category.direct_close");
    default:
      return (t) => t("inbox.rule.category.other");
  }
}

/**
 * Lo que un control de cumplimiento encontro, en una frase (E3, 2026-10-12).
 *
 * Una frase por cada `FindingCode` del servidor. Un codigo que esta version no conoce
 * **no se pinta crudo**: se dice que hay un hallazgo y que lo revisa el ajustador.
 */
export function findingLabel(code: string): Message {
  switch (code) {
    case "disclosure_missing":
      return (t) => t("inbox.controls.finding.disclosure_missing");
    case "human_route_missed":
      return (t) => t("inbox.controls.finding.human_route_missed");
    case "pii_found":
      return (t) => t("inbox.controls.finding.pii_found");
    case "attachment_missing":
      return (t) => t("inbox.controls.finding.attachment_missing");
    default:
      return (t) => t("inbox.controls.finding.other");
  }
}
