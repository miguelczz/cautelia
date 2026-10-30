// El registro de pantallas visitables que recorre el arnes (entidad
// VisitableRoute; BR7.1, AC1.33.1).
//
// Cada unidad con pantallas agrega aqui las suyas **en el mismo cambio** en que
// las agrega al enrutador: la comprobacion de completitud
// (`src/app/visitable-routes.test.ts`, que `mise run a11y` corre primero) compara
// las rutas del enrutador con este registro y falla nombrando la que falte.
//
// `path` lleva los parametros de ejemplo ya puestos, para que el arnes abra la
// pantalla sin adivinar. El de la aseguradora es **uno real**, como en un caso
// de golden set: con uno inventado la pagina llama a rutas que no existen y el
// arnes falla por los errores de consola. Por eso esta carpeta esta entre las
// que el chequeo de identificadores literales admite. `readiness` marca las dos paginas de la espera, que no
// son rutas: el arnes las obtiene interceptando la salud de listo.

import type { ExampleCaseList, QualityBoard, SiteDirectory, SpendPanel } from "../src/shared/api";

export type Audience = "visitor" | "staff";

export interface VisitableRoute {
  /** Identificador estable, el que nombra el reporte del arnes. */
  readonly routeId: string;
  /** La ruta del enrutador que cubre; `(not-found)` y `(readiness)` no son rutas. */
  readonly route: string;
  /** La direccion concreta que abre el arnes. */
  readonly path: string;
  readonly owningUnit: string;
  /** Un hallazgo serio o critico bloquea en `visitor`; en `staff` se reporta (D25). */
  readonly audience: Audience;
  /** El estado sembrado que necesita, si alguno. */
  readonly needsSeed?: string;
  /**
   * Esta direccion solo redirige a otra pantalla registrada, que ya se mide por su
   * cuenta en los dos idiomas y los dos modos. Aqui se comprueba que **se dibuja**
   * --que la redireccion llega--, y la accesibilidad no se mide dos veces: es la
   * misma pagina, y el arnes tiene un presupuesto de tiempo (PERF-U6.3, 2026-10-11).
   */
  readonly redirectsTo?: string;
  /** Las dos paginas de la espera del proceso (functional-spec 2.1). */
  readonly readiness?: "waking" | "unavailable";
  /**
   * Las respuestas con las que el arnes atiende la API de esta pantalla.
   *
   * **Por que hace falta.** El arnes corre contra el proceso real sobre una base
   * **vacia**: no hay casos sembrados ni enlaces emitidos, asi que las pantallas de
   * la bandeja se dibujarian todas como "no hay nada aqui" y lo que entraria en la
   * linea base de accesibilidad seria una pagina de estado, no la pantalla. Con esto
   * el arnes sirve una respuesta declarada y versionada, y mide **el dibujo real**:
   * contraste, encabezados, orden de tabulacion, objetivos tactiles. Es el mismo
   * recurso que ya usaban las dos paginas de la espera, que interceptan la salud de
   * listo.
   *
   * Lo que **no** sustituye: las reglas de acceso. Que una credencial no vea casos
   * de otra aseguradora y que un enlace abra solo su caso se prueban contra la base
   * de verdad, en las pruebas de integracion de U14, y ahi siguen.
   */
  readonly stub?: readonly {
    /** El patron de ruta que atiende, tal como lo entiende Playwright. */
    readonly url: string;
    /** El cuerpo JSON con el que responde. */
    readonly body: unknown;
    /** Un flujo de eventos en vez de JSON: solo su senal de apertura. */
    readonly sse?: boolean;
  }[];
}

/**
 * Un caso de ejemplo para el arnes: los seis bloques con algo en cada uno.
 *
 * Con algo en cada uno **a proposito**: una pantalla con los bloques vacios no tiene
 * casi nada que analizar, y lo que hay que medir es la vista llena. Los datos son
 * sinteticos y no salen de ninguna persona; el texto de la conversacion lleva sus
 * etiquetas de redaccion puestas, como las lleva de verdad.
 */
const CASO_DE_EJEMPLO = {
  case_id: "case-a11y",
  case_number: "SA-1",
  state: "derived",
  record_type: "claim",
  channel: "chat",
  language: "es",
  priority: "high",
  derivation_reason: "rule",
  completeness_complete: 5,
  completeness_total: 7,
  fields: [
    {
      field_key: "identity_and_policy",
      status: "confirmed",
      complete: true,
      label_key: "case.field.identity_and_policy",
    },
    {
      field_key: "injuries",
      status: "not_stated",
      complete: false,
      label_key: "case.field.injuries",
    },
  ],
  transcript: [
    {
      turn_id: "t1",
      speaker: "insured",
      text_redacted: "Choque mi carro, placa [PLACA].",
      started_at: "2026-09-28T12:00:00+00:00",
    },
    {
      turn_id: "t2",
      speaker: "agent",
      text_redacted: "Dejeme revisar su poliza, un momento.",
      started_at: "2026-09-28T12:00:20+00:00",
    },
  ],
  coverage_answers: [
    {
      answer_id: "a1",
      outcome: "verified",
      question_redacted: "Cubre el vidrio?",
      citations: [
        {
          clause_id: "PAP-2026-STO-001-4.1",
          clause_version: "2026.1",
          part: "Part D",
          text: "La compania responde por los danos al vehiculo asegurado.",
          clause_language: "es",
          amount_deferred: false,
          issuer_label: "Seguros Aburrá",
        },
      ],
    },
  ],
  rule_category: "referral",
  fired_rules: ["injuries-present"],
  controls_ok: true,
  control_findings: [],
  trace_status: "ready",
  trace_cost_usd: "0.0031",
  trace_cost_status: "measured",
  trace_latency_ms: 1800,
  updated_at: "2026-09-28T12:01:00+00:00",
  resolution: null,
  available_actions: ["approve", "reject"],
  can_correct_fields: true,
  explanation: {
    asked: "present",
    cited: "present",
    rule: "present",
    decided_by: "pending",
    decided_at: "pending",
    decided_by_kind: null,
    decided_by_id: null,
    decided_at_iso: null,
  },
};

/**
 * El tablero de gasto de ejemplo: treinta dias con gasto, las cuatro actividades,
 * consultas sin precio y dos casos (uno del propio navegador), para que el arnes
 * mida la vista llena y no la de "no hay nada". Importes sinteticos; ningun
 * identificador de caso.
 */
// Tipado con el contrato generado a proposito: `body: unknown` dejo que esta
// respuesta se quedara sin `top_cases` cuando la pantalla ya lo dibujaba, y el
// arnes --lo unico que la alimenta con un cuerpo fijo-- se cayo en la tuberia con
// un `undefined.length`. Con el tipo, el siguiente campo del contrato rompe `tsc`
// aqui, antes de gastar un navegador.
/** La ultima evaluacion, con un fallo que detiene la entrega y una regla sin medir:
 *  lo que mas ancho pide la pantalla y lo que el recorrido tiene que poder leer. */
const CALIDAD_DE_EJEMPLO: QualityBoard = {
  run_id: "run-ejemplo",
  commit_sha: "abc1234def5678",
  produced_at: "2026-10-11T17:30:00Z",
  duration_seconds: 372,
  comparable: false,
  dirty_tree: false,
  models: ["claude-haiku-5-5", "gemini-3.5-flash-lite", "gemini-embedding-001"],
  totals: {
    es: { passed: 80, failed: 5, not_measured: 4 },
    en: { passed: 82, failed: 3, not_measured: 4 },
  },
  datasets: ["DS-2", "DS-3", "DS-6", "DS-8"].map((dataset) => ({
    dataset,
    by_language: {
      es: { passed: 17, failed: 2, not_measured: 1 },
      en: { passed: 19, failed: 1, not_measured: 0 },
    },
  })),
  gates: (
    ["citations", "no_promises", "personal_data", "isolation", "conduct", "content"] as const
  ).map((family) => ({
    family,
    by_language:
      family === "isolation"
        ? { es: {}, en: {} }
        : { es: { passed: 20, failed: 0 }, en: { passed: 19, failed: 1 } },
  })),
  failures: [
    {
      case_key: "DS-3/en/coverage-question-with-a-long-identifier",
      dataset: "DS-3",
      language: "en",
      criteria: ["citation_exists_coverage_question_with_a_long_identifier"],
      blocking: true,
      root_cause: null,
    },
    {
      case_key: "DS-2/es/understand-claim-without-keywords",
      dataset: "DS-2",
      language: "es",
      criteria: ["understanding_claim_without_keywords"],
      blocking: false,
      root_cause: "extraction",
    },
  ],
  not_measured: [{ cause: "target_unavailable", count: 8 }],
};

const GASTO_DE_EJEMPLO: SpendPanel = {
  window: {
    window_start: "2026-09-16",
    window_end: "2026-12-15",
    spent: { measured_usd: "0.68", unmeasured_count: 0 },
    cap_usd: "40.00",
    alert_usd: "24.00",
    recording_reserve_usd: { amount_usd: "1.49", status: "measured" },
    recording_spent: { measured_usd: "0", unmeasured_count: 0 },
    public_remaining_usd: { amount_usd: "37.83", status: "measured" },
    recording_remaining_usd: { amount_usd: "1.49", status: "measured" },
    status: "ok",
  },
  alert_sent_at: null,
  total: { measured_usd: "0.68", unmeasured_count: 571 },
  by_activity: [
    { activity: "calls", total: { measured_usd: "0.30", unmeasured_count: 0 } },
    { activity: "chat", total: { measured_usd: "0.046", unmeasured_count: 2 } },
    { activity: "quality_tests", total: { measured_usd: "0.34", unmeasured_count: 0 } },
    {
      activity: "policy_reading",
      total: { measured_usd: "0", unmeasured_count: 569 },
      unpriced: { tokens: 142000, uncounted: 0, free_plan: true },
    },
  ],
  by_provider: [
    {
      provider: "anthropic",
      total: { measured_usd: "0.38", unmeasured_count: 0 },
      models: [{ model: "claude-haiku-5-5", total: { measured_usd: "0.38", unmeasured_count: 0 } }],
    },
    {
      provider: "cartesia",
      total: { measured_usd: "0.24", unmeasured_count: 0 },
      models: [{ model: "sonic-3.6", total: { measured_usd: "0.24", unmeasured_count: 0 } }],
    },
    { provider: "deepgram", total: { measured_usd: "0.062", unmeasured_count: 0 } },
    {
      provider: "gemini",
      total: { measured_usd: "0.0042", unmeasured_count: 571 },
      unpriced: { tokens: 142000, uncounted: 0, free_plan: true },
    },
  ],
  by_day: [
    {
      day: "2026-09-10",
      activities: [
        { activity: "calls", total: { measured_usd: "0.031", unmeasured_count: 0 } },
        { activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } },
      ],
    },
    { day: "2026-09-11", activities: [] },
    {
      day: "2026-09-12",
      activities: [{ activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } }],
    },
    {
      day: "2026-09-13",
      activities: [{ activity: "calls", total: { measured_usd: "0.031", unmeasured_count: 0 } }],
    },
    {
      day: "2026-09-14",
      activities: [{ activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } }],
    },
    { day: "2026-09-15", activities: [] },
    {
      day: "2026-09-16",
      activities: [
        { activity: "calls", total: { measured_usd: "0.031", unmeasured_count: 0 } },
        { activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } },
      ],
    },
    { day: "2026-09-17", activities: [] },
    {
      day: "2026-09-18",
      activities: [{ activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } }],
    },
    {
      day: "2026-09-19",
      activities: [{ activity: "calls", total: { measured_usd: "0.031", unmeasured_count: 0 } }],
    },
    {
      day: "2026-09-20",
      activities: [{ activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } }],
    },
    { day: "2026-09-21", activities: [] },
    {
      day: "2026-09-22",
      activities: [
        { activity: "calls", total: { measured_usd: "0.031", unmeasured_count: 0 } },
        { activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } },
      ],
    },
    { day: "2026-09-23", activities: [] },
    {
      day: "2026-09-24",
      activities: [{ activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } }],
    },
    {
      day: "2026-09-25",
      activities: [{ activity: "calls", total: { measured_usd: "0.031", unmeasured_count: 0 } }],
    },
    {
      day: "2026-09-26",
      activities: [{ activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } }],
    },
    { day: "2026-09-27", activities: [] },
    {
      day: "2026-09-28",
      activities: [
        { activity: "calls", total: { measured_usd: "0.031", unmeasured_count: 0 } },
        { activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } },
      ],
    },
    { day: "2026-09-29", activities: [] },
    {
      day: "2026-09-30",
      activities: [{ activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } }],
    },
    {
      day: "2026-10-01",
      activities: [{ activity: "calls", total: { measured_usd: "0.031", unmeasured_count: 0 } }],
    },
    {
      day: "2026-10-02",
      activities: [{ activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } }],
    },
    { day: "2026-10-03", activities: [] },
    {
      day: "2026-10-04",
      activities: [
        { activity: "calls", total: { measured_usd: "0.031", unmeasured_count: 0 } },
        { activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } },
      ],
    },
    { day: "2026-10-05", activities: [] },
    {
      day: "2026-10-06",
      activities: [{ activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } }],
    },
    {
      day: "2026-10-07",
      activities: [
        { activity: "calls", total: { measured_usd: "0.031", unmeasured_count: 0 } },
        { activity: "quality_tests", total: { measured_usd: "0.21", unmeasured_count: 0 } },
      ],
    },
    {
      day: "2026-10-08",
      activities: [{ activity: "chat", total: { measured_usd: "0.004", unmeasured_count: 0 } }],
    },
    { day: "2026-10-09", activities: [] },
  ],
  calls: { count: 9, total: { measured_usd: "0.28", unmeasured_count: 0 } },
  chats: { count: 14, total: { measured_usd: "0.031", unmeasured_count: 0 } },
  cases: [
    {
      key: "0",
      tenant_id: "sunmeadow",
      record_type: "claim",
      channel: "voice",
      started_at: "2026-10-09T20:20:00+00:00",
      yours: true,
      total: { measured_usd: "0.031", unmeasured_count: 0 },
      by_provider: [
        { provider: "cartesia", total: { measured_usd: "0.024", unmeasured_count: 0 } },
        { provider: "deepgram", total: { measured_usd: "0.006", unmeasured_count: 0 } },
        { provider: "anthropic", total: { measured_usd: "0.001", unmeasured_count: 0 } },
      ],
    },
    {
      key: "1",
      tenant_id: "stonecroft",
      record_type: "coverage_inquiry",
      channel: "chat",
      started_at: "2026-10-09T19:05:00+00:00",
      yours: false,
      total: { measured_usd: "0.0021", unmeasured_count: 1 },
      by_provider: [
        { provider: "anthropic", total: { measured_usd: "0.0021", unmeasured_count: 0 } },
        {
          provider: "gemini",
          total: { measured_usd: "0", unmeasured_count: 1 },
          unpriced: { tokens: 480, uncounted: 0, free_plan: true },
        },
      ],
      unpriced: { tokens: 480, uncounted: 0, free_plan: true },
    },
  ],
  // Las tres consultas de un mismo clic en "Comparar", como una sola entrada.
  comparisons: [
    {
      key: "c0",
      started_at: "2026-10-09T20:02:00+00:00",
      yours: false,
      total: { measured_usd: "0.000684", unmeasured_count: 3 },
      unpriced: { tokens: 1440, uncounted: 0, free_plan: true },
      parts: [
        {
          tenant_id: "stonecroft",
          total: { measured_usd: "0.000684", unmeasured_count: 1 },
          unpriced: { tokens: 480, uncounted: 0, free_plan: true },
        },
        {
          tenant_id: "knotwell",
          total: { measured_usd: "0", unmeasured_count: 1 },
          unpriced: { tokens: 480, uncounted: 0, free_plan: true },
        },
        {
          tenant_id: "sunmeadow",
          total: { measured_usd: "0", unmeasured_count: 1 },
          unpriced: { tokens: 480, uncounted: 0, free_plan: true },
        },
      ],
    },
  ],
};

// Tipado con el contrato generado, como el panel de gasto: el dia que el directorio
// crezca, `tsc` rompe aqui y no el arnes. Ya crecio una vez --la tanda 2 de U23 le
// anadio quien emitio la poliza de ejemplo de una agencia-- y por eso la respuesta
// declarada de abajo lo trae: con el, el arnes mide **la vista llena** de la
// comparacion y no el estado "divulgacion incompleta".
const DIRECTORIO_DE_EJEMPLO: SiteDirectory = {
  tenants: [
    {
      tenant_id: "sunmeadow",
      display_name: "Autos Poblado",
      kind: "carrier",
      default_language: "en",
      example_policy: "POL-21",
      agent_name: "Catalina",
    },
    {
      tenant_id: "stonecroft",
      display_name: "Seguros Aburrá",
      kind: "carrier",
      default_language: "es",
      example_policy: "POL-11",
      agent_name: "Catalina",
    },
    {
      tenant_id: "knotwell",
      display_name: "Agencia Castilla",
      kind: "agency",
      default_language: "en",
      example_policy: "POL-31",
      agent_name: "Catalina",
      // La agencia nombra a quien emitio su poliza (U23, BR1.2). Con esto el arnes
      // mide **la vista llena** y no el estado "divulgacion incompleta", que era lo
      // que medía mientras el contrato no traia el emisor.
      example_policy_issuer: "Autos Poblado",
    },
  ],
  surfaces: ["comparison"],
  links: {},
};

/**
 * Los casos de ejemplo de una aseguradora, para la pagina "Casos": tres estados, uno con
 * dos filas, para que el arnes mida la lista llena y no la de "no hay nada". Tipado con el
 * contrato generado, como el panel de gasto. Ningun numero ni identificador es de un
 * visitante: son los del generador.
 */
const CASOS_DE_EJEMPLO_DE_UNA_ASEGURADORA: ExampleCaseList = {
  items: [
    {
      case_id: "case-a11y-capturando",
      case_number: "SA-3",
      record_type: "claim",
      state: "capturing",
      channel: "chat",
      language: "es",
      completeness_complete: 2,
      completeness_total: 7,
    },
    {
      case_id: "case-a11y",
      case_number: "SA-1",
      record_type: "claim",
      state: "derived",
      channel: "chat",
      language: "es",
      completeness_complete: 5,
      completeness_total: 7,
    },
    {
      case_id: "case-a11y-consulta",
      case_number: "SA-2",
      record_type: "coverage_inquiry",
      state: "derived",
      channel: "voice",
      language: "en",
      completeness_complete: 1,
      completeness_total: 1,
    },
    {
      case_id: "case-a11y-cerrado",
      case_number: "SA-4",
      record_type: "claim",
      state: "closed",
      channel: "chat",
      language: "en",
      completeness_complete: 7,
      completeness_total: 7,
    },
  ],
};

export const VISITABLE_ROUTES: readonly VisitableRoute[] = [
  // La raiz del aplicativo redirige a /home: en cautelia.app la raiz es la
  // landing, servida antes de llegar al enrutador (decision de Miguel, 2026-10-06).
  { routeId: "root_redirect", route: "/", path: "/", owningUnit: "U6", audience: "visitor" },
  { routeId: "home", route: "/home", path: "/home", owningUnit: "U6", audience: "visitor" },
  {
    routeId: "guide",
    route: "/how-it-works",
    path: "/how-it-works",
    owningUnit: "U6",
    audience: "visitor",
  },
  {
    routeId: "status-link-invalid",
    route: "/status/$kind",
    path: "/status/link_invalid",
    owningUnit: "U6",
    audience: "visitor",
  },
  {
    routeId: "status-link-expired",
    route: "/status/$kind",
    path: "/status/link_expired",
    owningUnit: "U6",
    audience: "visitor",
  },
  {
    routeId: "status-data-reset",
    route: "/status/$kind",
    path: "/status/data_reset",
    owningUnit: "U6",
    audience: "visitor",
  },
  {
    routeId: "status-not-found",
    route: "/status/$kind",
    path: "/status/not_found",
    owningUnit: "U6",
    audience: "visitor",
  },
  {
    routeId: "status-service-unavailable",
    route: "/status/$kind",
    path: "/status/service_unavailable",
    owningUnit: "U6",
    audience: "visitor",
  },
  {
    routeId: "not-found",
    route: "(not-found)",
    path: "/esta-pagina-no-existe",
    owningUnit: "U6",
    audience: "visitor",
  },
  {
    routeId: "telemetry",
    route: "/telemetry",
    path: "/telemetry",
    owningUnit: "U22",
    audience: "visitor",
    stub: [{ url: "**/api/spend", body: GASTO_DE_EJEMPLO }],
  },
  {
    routeId: "telemetry-quality",
    route: "/telemetry",
    path: "/telemetry?view=quality",
    owningUnit: "U22",
    audience: "visitor",
    stub: [{ url: "**/api/quality", body: CALIDAD_DE_EJEMPLO }],
  },
  {
    // La direccion de antes: lleva a la pestana de resultados.
    routeId: "metrics",
    route: "/metrics",
    path: "/metrics",
    redirectsTo: "telemetry-quality",
    owningUnit: "U22",
    audience: "visitor",
    stub: [{ url: "**/api/quality", body: CALIDAD_DE_EJEMPLO }],
  },
  {
    routeId: "policies",
    route: "/policies",
    path: "/policies",
    owningUnit: "U13",
    audience: "visitor",
  },
  {
    // El caso propio sale del chat de este navegador (sin conversacion, la pagina dice
    // que no hay ninguno) y los de ejemplo se sirven declarados.
    routeId: "cases",
    route: "/cases",
    path: "/cases",
    owningUnit: "U14",
    audience: "visitor",
    stub: [{ url: "**/api/examples/*/cases", body: CASOS_DE_EJEMPLO_DE_UNA_ASEGURADORA }],
  },
  {
    routeId: "example-case",
    route: "/cases/$tenantId/$caseId",
    path: "/cases/stonecroft/case-a11y",
    owningUnit: "U14",
    // **Visitante**: es una pagina publica y sus hallazgos bloquean (D25). Sin acciones,
    // como la sirve el servidor para un caso de ejemplo.
    audience: "visitor",
    stub: [
      {
        url: "**/api/examples/*/cases/*",
        body: { ...CASO_DE_EJEMPLO, available_actions: [], can_correct_fields: false },
      },
    ],
  },
  {
    // La direccion de antes: lleva a la pestana del gasto.
    routeId: "spend",
    route: "/spend",
    path: "/spend",
    redirectsTo: "telemetry",
    owningUnit: "U22",
    audience: "visitor",
    stub: [{ url: "**/api/spend", body: GASTO_DE_EJEMPLO }],
  },
  {
    routeId: "comparison",
    route: "/compare",
    path: "/compare",
    owningUnit: "U23",
    audience: "visitor",
    stub: [{ url: "**/api/site", body: DIRECTORIO_DE_EJEMPLO }],
  },
  {
    routeId: "chat",
    route: "/t/$tenantId/chat",
    path: "/t/stonecroft/chat",
    owningUnit: "U13",
    audience: "visitor",
  },
  {
    routeId: "voice-console",
    route: "/t/$tenantId/call",
    path: "/t/stonecroft/call",
    owningUnit: "U16",
    audience: "visitor",
    // La consola arranca preguntando si hay voz, y sobre la base vacia del arnes
    // esa respuesta depende del techo de gasto, que no se puede leer. Sin esta
    // respuesta declarada, lo que entraria en la linea base de accesibilidad
    // seria la pantalla de "no hay voz" y no la consola.
    stub: [
      {
        url: "**/api/voice/*/availability",
        body: {
          available: true,
          reason_code: null,
          reason_key: null,
          voice_mode: "primary",
          limits: {
            max_call_seconds: 180,
            warn_at_seconds: 30,
            resume_window_seconds: 900,
            calls_per_visitor_day: null,
            calls_per_site_day: null,
          },
          resume_until: null,
        },
      },
    ],
  },
  {
    routeId: "trace-summary",
    route: "/t/$tenantId/trace/$traceId",
    path: "/t/stonecroft/trace/tr-de-ejemplo",
    owningUnit: "U13",
    audience: "visitor",
  },
  {
    routeId: "inbox-queue",
    route: "/t/$tenantId/inbox",
    path: "/t/stonecroft/inbox?priority=high",
    owningUnit: "U14",
    // D25: la cola y la vista con credencial se recorren igual en los dos idiomas y
    // los dos modos, y sus hallazgos se reportan; el que bloquea es el de la pantalla
    // del visitante, que es la que entra en la linea base.
    audience: "staff",
    stub: [
      // El flujo de avisos, con su senal de apertura y nada mas. Sin declararlo, la
      // pantalla abre un `EventSource` contra una ruta que sin credencial rechaza, y
      // el rechazo queda como un error en la consola de una pagina que funciona.
      { url: "**/api/inbox/*/stream", body: null, sse: true },
      {
        url: "**/api/inbox/*/cases?*",
        body: {
          items: [
            {
              case_id: "case-a11y",
              case_number: "SA-1",
              state: "derived",
              record_type: "claim",
              channel: "chat",
              language: "es",
              priority: "high",
              completeness: 0.71,
              completeness_complete: 5,
              completeness_total: 7,
              derivation_reason: "rule",
              updated_at: "2026-09-28T12:01:00+00:00",
            },
          ],
          next_cursor: null,
        },
      },
    ],
  },
  {
    routeId: "inbox-case",
    route: "/t/$tenantId/inbox/$caseId",
    path: "/t/stonecroft/inbox/case-a11y",
    owningUnit: "U14",
    audience: "staff",
    stub: [
      { url: "**/api/inbox/*/stream", body: null, sse: true },
      { url: "**/api/inbox/*/cases/*", body: CASO_DE_EJEMPLO },
    ],
  },
  {
    routeId: "case-link-redeem",
    route: "/c",
    // Sin token en el fragmento: es la pantalla que se dibuja cuando el enlace no
    // vale, y **es visitante**, asi que sus hallazgos bloquean (D25).
    path: "/c",
    owningUnit: "U14",
    audience: "visitor",
  },
  {
    routeId: "visitor-case",
    route: "/c/$tenantId/$caseId",
    path: "/c/stonecroft/case-a11y",
    owningUnit: "U14",
    // **La que entra en la linea base** (D25): un hallazgo serio o critico aqui
    // bloquea la entrega.
    audience: "visitor",
    stub: [{ url: "**/api/inbox/*/cases/*", body: CASO_DE_EJEMPLO }],
  },
  {
    routeId: "waking",
    route: "(readiness)",
    path: "/",
    owningUnit: "U6",
    audience: "visitor",
    readiness: "waking",
  },
  {
    routeId: "unavailable",
    route: "(readiness)",
    path: "/",
    owningUnit: "U6",
    audience: "visitor",
    readiness: "unavailable",
  },
];
