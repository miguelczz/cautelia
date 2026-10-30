import { describe, expect, it } from "vitest";

import type {
  CaseDetailOut,
  CaseState,
  Channel,
  InboxAction,
  Priority,
  RecordType,
} from "../../shared/api-client/inbox";
import EN from "../../shared/copy/copy-texts.en";
import ES from "../../shared/copy/copy-texts.es";

const COPY_TEXTS = new Map<Locale, typeof ES>([
  ["es", ES],
  ["en", EN],
]);
import type { Locale } from "../../shared/copy/copy-keys";
import { createTranslate } from "../../shared/i18n/translate";
import {
  actionLabel,
  caseReasonLabel,
  channelLabel,
  coverageOutcomeLabel,
  derivationReasonLabel,
  fieldLabel,
  findingLabel,
  isClosedByRules,
  isUnderReview,
  KNOWN_FIELD_LABEL_KEYS,
  ownCaseTitle,
  priorityLabel,
  recordTypeLabel,
  resolutionLabel,
  reviewHint,
  ruleCategoryLabel,
  ruleReasonLabel,
  stateLabel,
  waitedLabel,
} from "./inbox-labels";

// Ningun valor interno se imprime hacia una persona (SEC-U4.15), y las cuatro
// salidas de cobertura se ven distintas (BR2.5).

const IDIOMAS: readonly Locale[] = ["es", "en"];
const ESTADOS: readonly CaseState[] = [
  "open",
  "capturing",
  "verifying",
  "deciding",
  "derived",
  "awaiting_insured",
  "closed",
];
const TIPOS: readonly RecordType[] = ["claim", "coverage_inquiry", "quote_request"];
const CANALES: readonly Channel[] = ["voice", "chat"];
const PRIORIDADES: readonly Priority[] = ["high", "normal"];
const ACCIONES: readonly InboxAction[] = ["approve", "reject", "mark_sent"];
const RESOLUCIONES = ["registered", "approved", "rejected", "sent_to_insurer"] as const;
const MOTIVOS = ["demo_limit", "person_requested", "rule"] as const;
const COBERTURA = ["verified", "rejected", "no_clause_found", "unverifiable"] as const;

describe.each(IDIOMAS)("las etiquetas de la bandeja en %s", (idioma) => {
  const t = createTranslate(idioma);

  it("ningun valor interno del caso llega a la pantalla", () => {
    // Si la etiqueta fuera el propio valor --`awaiting_insured`-- una pantalla que se
    // olvidara de resolverla imprimiria el valor interno y se veria "casi bien", que
    // es la forma mas facil de que se quede asi.
    const resueltas = [
      ...ESTADOS.map((v) => [v, stateLabel(v)(t)] as const),
      ...TIPOS.map((v) => [v, recordTypeLabel(v)(t)] as const),
      ...CANALES.map((v) => [v, channelLabel(v)(t)] as const),
      ...PRIORIDADES.map((v) => [v, priorityLabel(v)(t)] as const),
      ...ACCIONES.map((v) => [v, actionLabel(v)(t)] as const),
      ...RESOLUCIONES.map((v) => [v, resolutionLabel(v)(t)] as const),
      ...MOTIVOS.map((v) => [v, derivationReasonLabel(v)(t)] as const),
      ...COBERTURA.map((v) => [v, coverageOutcomeLabel(v)(t)] as const),
    ];

    for (const [valor, etiqueta] of resueltas) {
      expect(etiqueta, `'${valor}' no tiene etiqueta`).not.toBe("");
      expect(etiqueta, `'${valor}' se imprime tal cual`).not.toBe(valor);
      expect(etiqueta).not.toContain(".");
    }
  });

  it("las cuatro salidas de cobertura se leen distintas entre si (BR2.5)", () => {
    // Dos claves distintas con el mismo texto colapsan los dos resultados igual que
    // una sola clave. Lo que la regla protege es que "sin clausula" y "no pude
    // verificar" no se confundan, y eso se ve en el texto, no en la clave.
    const frases = COBERTURA.map((salida) => coverageOutcomeLabel(salida)(t));

    expect(new Set(frases).size).toBe(COBERTURA.length);
  });

  it("un valor que esta version no conoce se dice de alguna manera, nunca vacio", () => {
    // Es la rama por defecto de `problems.ts` aplicada aqui: un hueco parece un
    // problema de maquetacion y se busca donde no es.
    expect(coverageOutcomeLabel("una-salida-nueva")(t)).not.toBe("");
    expect(resolutionLabel("una-resolucion-nueva")(t)).not.toBe("");
    expect(fieldLabel("case.field.inventado")(t)).not.toBe("");
  });

  it("sin motivo de derivacion se dice con palabras, no con un hueco", () => {
    expect(derivationReasonLabel(null)(t)).toBe(t("inbox.case.no_reason"));
  });
});

describe("las etiquetas de los campos del caso", () => {
  it("cubre cada clave de campo del catalogo, en los dos sentidos", () => {
    // La cadena completa es esta, en tres eslabones: la prueba de U4 ata el esquema
    // de campos al catalogo (los dos sentidos), el servidor manda la clave, y esta
    // prueba ata el catalogo a la tabla de la pantalla. Sin este eslabon, un campo
    // nuevo se dibujaria como "no disponible" sin que nada fallara.
    //
    // Se compara contra el catalogo generado y **no** contra el esquema del servidor,
    // que esta fuera de este proyecto: seria una tercera copia de la misma lista, y
    // la que un dia se queda atras es siempre la tercera.
    const frases = COPY_TEXTS.get("es");
    expect(frases).toBeDefined();
    const delCatalogo = new Set(
      [...(frases ?? new Map<string, string>()).keys()].filter((clave: string) =>
        clave.startsWith("case.field."),
      ),
    );
    const deLaPantalla = new Set(
      KNOWN_FIELD_LABEL_KEYS.filter((clave) => clave.startsWith("case.field.")),
    );

    expect([...deLaPantalla].sort()).toEqual([...delCatalogo].sort());
    expect(delCatalogo.size).toBeGreaterThan(0);
  });
});

// Cuando la agente aun evalua el caso, o lo cerraron las reglas sin ajustador (US1.17).
describe("los estados de evaluacion y el cierre directo", () => {
  const explicacion = (quien: string | null): CaseDetailOut["explanation"] => ({
    asked: "none",
    cited: "none",
    rule: "present",
    decided_by: quien === null ? "pending" : "present",
    decided_at: quien === null ? "pending" : "present",
    decided_by_kind: quien,
    decided_by_id: null,
    decided_at_iso: quien === null ? null : "2026-09-28T12:30:00+00:00",
  });
  const detalle = (state: CaseState, resolution: string | null, quien: string | null) =>
    ({ state, resolution, explanation: explicacion(quien) }) as CaseDetailOut;

  it("solo verifying y deciding estan en evaluacion", () => {
    const enEvaluacion = ESTADOS.filter((estado) => isUnderReview(estado));

    expect(enEvaluacion).toEqual(["verifying", "deciding"]);
  });

  it("cada estado de evaluacion tiene su frase, y los demas no", () => {
    const t = createTranslate("es");

    for (const estado of ESTADOS) {
      const frase = reviewHint(estado);
      if (isUnderReview(estado)) {
        expect(frase?.(t)).toBeTruthy();
        // No dice que el caso esta con un ajustador: todavia no lo esta.
        expect(frase?.(t)).not.toMatch(/ajustador/);
      } else {
        expect(frase).toBeUndefined();
      }
    }
    expect(reviewHint("verifying")?.(t)).not.toBe(reviewHint("deciding")?.(t));
  });

  it("un cierre directo es cerrado, registrado y del sistema: las tres a la vez", () => {
    expect(isClosedByRules(detalle("closed", "registered", "system"))).toBe(true);
    // Cada una de las tres por separado no basta.
    expect(isClosedByRules(detalle("deciding", "registered", "system"))).toBe(false);
    expect(isClosedByRules(detalle("closed", "approved", "system"))).toBe(false);
    expect(isClosedByRules(detalle("closed", "registered", "staff"))).toBe(false);
    expect(isClosedByRules(detalle("closed", "registered", "insured"))).toBe(false);
    expect(isClosedByRules(detalle("closed", null, null))).toBe(false);
  });

  // El renglon «Por que llego aqui» (2026-10-13): «sin motivo de derivacion registrado» se
  // leia como un dato que faltaba en un caso que nunca llego a un ajustador.
  describe("el renglon «por que llego aqui»", () => {
    const conMotivo = (base: CaseDetailOut, motivo: string | null): CaseDetailOut => ({
      ...base,
      derivation_reason: motivo,
    });

    it.each(IDIOMAS)("un cierre directo dice que no paso por un ajustador (%s)", (idioma) => {
      const t = createTranslate(idioma);
      const cierre = conMotivo(detalle("closed", "registered", "system"), null);

      const frase = caseReasonLabel(cierre)(t);

      expect(frase).toBe(t("inbox.case.not_handed_off"));
      expect(frase).not.toBe(t("inbox.case.no_reason"));
      expect(frase).not.toBe("");
    });

    it("en espanol dice «ajustador», no «una persona»", () => {
      const t = createTranslate("es");
      const frase = caseReasonLabel(conMotivo(detalle("closed", "registered", "system"), null))(t);

      expect(frase).toMatch(/ajustador/);
      expect(frase).not.toMatch(/persona/i);
    });

    it.each(["verifying", "deciding"] as const)(
      "con la agente evaluando (%s) dice que la agente lo esta revisando",
      (estado) => {
        const t = createTranslate("es");
        const frase = caseReasonLabel(conMotivo(detalle(estado, null, null), null))(t);

        expect(frase).toBe(reviewHint(estado)?.(t));
        expect(frase).not.toBe(t("inbox.case.no_reason"));
      },
    );

    it("los demas estados sin motivo siguen diciendo que no hay motivo registrado", () => {
      const t = createTranslate("es");
      const sinMotivo: readonly CaseDetailOut[] = [
        detalle("open", null, null),
        detalle("capturing", null, null),
        detalle("derived", null, null),
        detalle("awaiting_insured", null, null),
        // Cerrados, pero no por las reglas: la tercera pata de `isClosedByRules` falta o falla.
        detalle("closed", "approved", "staff"),
        detalle("closed", "registered", "staff"),
        detalle("closed", "approved", "system"),
        detalle("closed", null, null),
      ].map((base) => conMotivo(base, null));

      for (const caso of sinMotivo) {
        expect(caseReasonLabel(caso)(t), `${caso.state}/${String(caso.resolution)}`).toBe(
          t("inbox.case.no_reason"),
        );
      }
    });

    it("un motivo registrado se dice siempre, tambien con la agente evaluando", () => {
      const t = createTranslate("es");

      for (const motivo of MOTIVOS) {
        expect(caseReasonLabel(conMotivo(detalle("derived", null, null), motivo))(t)).toBe(
          derivationReasonLabel(motivo)(t),
        );
      }
      expect(caseReasonLabel(conMotivo(detalle("deciding", null, null), "rule"))(t)).toBe(
        t("case.derivation_reason.rule"),
      );
    });
  });
});

describe("cuanto lleva esperando un caso", () => {
  const AHORA = new Date("2026-09-28T12:00:00Z");
  const t = createTranslate("es");

  it.each([
    ["2026-09-28T11:59:30Z", "inbox.waited.just_now"],
    ["2026-09-28T11:55:00Z", "inbox.waited.minutes"],
    ["2026-09-28T09:00:00Z", "inbox.waited.hours"],
    ["2026-09-25T12:00:00Z", "inbox.waited.days"],
  ] as const)("%s se dice con %s", (desde, clave) => {
    // Cada frontera con su unidad: sin las cuatro, una sola rama pasaria por todas y
    // "hace 4320 min" seria un resultado valido.
    const dicho = waitedLabel(desde, AHORA)(t);
    expect(dicho).not.toBe("");
    expect(dicho).toBe(
      clave === "inbox.waited.just_now"
        ? t("inbox.waited.just_now")
        : clave === "inbox.waited.minutes"
          ? t("inbox.waited.minutes", { value: 5 })
          : clave === "inbox.waited.hours"
            ? t("inbox.waited.hours", { value: 3 })
            : t("inbox.waited.days", { value: 3 }),
    );
  });

  it("un instante en el futuro no dice una espera negativa", () => {
    // Un reloj adelantado en el navegador no puede producir "hace -3 min".
    expect(waitedLabel("2026-09-28T13:00:00Z", AHORA)(t)).toBe(t("inbox.waited.just_now"));
  });

  it("un instante ilegible no rompe la fila", () => {
    expect(waitedLabel("no es una fecha", AHORA)(t)).toBe(t("inbox.waited.just_now"));
  });
});

describe.each(IDIOMAS)(
  "lo que el caso dice de si mismo, en %s (C10 y E3, 2026-10-12)",
  (idioma) => {
    const t = createTranslate(idioma);

    it("cada tipo de caso se titula con palabras distintas y sin su codigo", () => {
      const titulos = TIPOS.map((tipo) => ownCaseTitle(tipo)(t));

      expect(new Set(titulos).size).toBe(TIPOS.length);
      for (const titulo of titulos) {
        expect(titulo).not.toBe("");
        expect(titulo).not.toMatch(/\{|_|[A-Z]{3}-\d/);
      }
    });

    it("cada categoria de las reglas tiene su frase, y una desconocida se dice sin imprimirla", () => {
      const frases = ["referral", "standard_review", "direct_close"].map((categoria) =>
        ruleReasonLabel(categoria)(t),
      );
      const desconocida = ruleReasonLabel("categoria_nueva")(t);

      expect(new Set([...frases, desconocida]).size).toBe(4);
      for (const frase of [...frases, desconocida]) {
        expect(frase).not.toMatch(/referral|standard_review|direct_close|categoria_nueva|_/);
      }
    });

    it("cada categoria de las reglas tiene su etiqueta corta, y una desconocida nunca se pinta cruda", () => {
      const categorias = ["referral", "standard_review", "direct_close"] as const;
      const etiquetas = categorias.map((categoria) => ruleCategoryLabel(categoria)(t));
      const otra = ruleCategoryLabel("categoria_nueva")(t);

      expect(new Set([...etiquetas, otra]).size).toBe(4);
      for (const etiqueta of [...etiquetas, otra]) {
        expect(etiqueta).not.toMatch(/referral|standard_review|direct_close|categoria_nueva|_/);
      }
    });

    it("cada codigo de hallazgo del servidor tiene su frase, y uno desconocido nunca se pinta crudo", () => {
      const codigos = ["disclosure_missing", "human_route_missed", "attachment_missing"] as const;
      const frases = codigos.map((codigo) => findingLabel(codigo)(t));
      const generica = findingLabel("hallazgo_nuevo")(t);

      expect(new Set([...frases, generica]).size).toBe(4);
      for (const frase of [...frases, generica]) {
        expect(frase).not.toMatch(/_/);
        expect(frase).not.toContain("hallazgo_nuevo");
      }
    });
  },
);
