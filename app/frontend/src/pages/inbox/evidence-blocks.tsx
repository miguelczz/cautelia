// Los seis bloques de evidencia de un caso (BR2.2).
//
// **Los seis van abiertos desde el 2026-10-12.** Los tres ultimos --la regla, los
// controles y la respuesta-- iban plegados y mostraban codigos (`referral`,
// `pii_found`, `No medido`): Miguel no les encontro sentido ("es una estupidez tener
// algo ahi que no se esta utilizando"). Ahora dicen en una frase lo que antes decian en
// clave, y **un bloque sin nada que decir no se pinta**: ni "No medido" ni una fila
// vacia. Sin plegar, tampoco queda un titulo con mas sangria que su contenido.
//
// **Los mismos bloques sirven a las dos pantallas** --la del ajustador con
// credencial y la del visitante con enlace--, que es lo unico que comparten
// (decision de Miguel, 2026-09-28). Lo que no comparten es la voz: las etiquetas de
// aqui son del registro de quien decide, y la pantalla del visitante las envuelve
// en el suyo. Por eso estas piezas no escriben ningun titulo de pagina ni ninguna
// frase de bienvenida: solo evidencia.
//
// **La transcripcion llega ya redactada de U3 y aqui no se destapa** (BR2.3). Lo que
// se dibuja son las etiquetas que U3 escribio; el valor completo vive en el campo
// del caso, que se ve en el bloque de arriba, y eso se dice con palabras para que
// corregirlo sea posible sin leerlo en la conversacion.

import { useId, useMemo, type ReactNode } from "react";

import type {
  CaseDetailOut,
  CaseFieldView,
  CoverageAnswerOut,
} from "../../shared/api-client/inbox";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Locale } from "../../shared/copy/copy-keys";
import type { Message } from "../../shared/i18n/translate";
import {
  isMasked,
  restoreAll,
  restoreTurns,
  type OwnTexts,
  type StoredTurn,
} from "../../shared/own-text/own-text";
import { BLOCK_TITLE } from "../../shared/ui/page-layout";
import { Tag } from "../../shared/ui/tag";
import { Citation, withPositions } from "../chat/citation";
import {
  coverageOutcomeLabel,
  fieldLabel,
  findingLabel,
  isClosedByRules,
  isUnderReview,
  ruleReasonLabel,
} from "./inbox-labels";

/** Un bloque abierto: su titulo y su contenido, siempre a la vista. */
export function OpenBlock({
  title,
  testId,
  children,
}: {
  readonly title: string;
  readonly testId: string;
  readonly children: ReactNode;
}) {
  return (
    <section
      aria-label={title}
      data-testid={testId}
      className="rounded-surface border border-hairline bg-surface p-4"
    >
      <h2 className={BLOCK_TITLE}>{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** La completitud campo por campo (bloque abierto). */
export function FieldCompleteness({
  fields,
  correctionFor,
}: {
  readonly fields: readonly CaseFieldView[];
  /** La correccion en linea de un campo, cuando la pantalla la ofrece (BR3.4). */
  readonly correctionFor?: (field: CaseFieldView) => ReactNode;
}) {
  const { t } = useLocale();
  return (
    <ul className="flex flex-col gap-2" data-testid="case-fields">
      {fields.map((campo) => {
        const anotado = campo.value ?? null;
        const opcional = campo.optional === true && !campo.complete;
        return (
          <li key={campo.field_key} className="flex flex-wrap items-start gap-2">
            {/* Lo anotado solo llega a quien abrio su propio caso con su enlace: el
                rotulo pasa a ser la etiqueta y debajo va lo que dijo. */}
            {anotado === null ? (
              <span className="min-w-0 flex-1">{fieldLabel(campo.label_key)(t)}</span>
            ) : (
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="text-caption text-fg-secondary">
                  {fieldLabel(campo.label_key)(t)}
                </span>
                <span className="whitespace-pre-line break-words" data-testid="field-value">
                  {anotado}
                </span>
              </span>
            )}
            <Tag tone={campo.complete ? "success" : opcional ? "neutral" : "warning"}>
              {campo.complete
                ? t("inbox.fields.complete")
                : opcional
                  ? t("inbox.fields.optional")
                  : t("inbox.fields.incomplete")}
            </Tag>
            {correctionFor?.(campo)}
          </li>
        );
      })}
    </ul>
  );
}

/** Quien dijo un turno, en los tres valores que entiende el texto propio. */
function voiceOf(speaker: string): StoredTurn["speaker"] {
  if (speaker === "insured") {
    return "visitor";
  }
  return speaker === "agent" ? "agent" : "other";
}

/**
 * La conversacion (bloque abierto, BR2.3).
 *
 * Llega redactada de U3 y la bandeja no la destapa. **Solo la destapa quien la escribio**
 * (2026-10-12, cuarta vez que Miguel lo pide): la pantalla propia le pasa `own`, lo que
 * este navegador recuerda de la conversacion, y cada turno tapado recupera su texto si
 * encaja con su forma. Sin `own` --la bandeja, el caso de ejemplo-- se queda como llego.
 *
 * La nota que explica las etiquetas solo sale si de verdad queda alguna a la vista: con
 * todo destapado seria una explicacion de algo que no se ve.
 */
export function TranscriptView({
  detail,
  own,
}: {
  readonly detail: CaseDetailOut;
  /** Lo que este navegador recuerda de esta conversacion, si la pantalla es de su dueno. */
  readonly own?: OwnTexts | undefined;
}) {
  const { t } = useLocale();
  const restaurados = useMemo(
    () =>
      own === undefined
        ? new Map<string, string>()
        : restoreTurns(
            detail.transcript.map((turno) => ({
              id: turno.turn_id,
              speaker: voiceOf(turno.speaker),
              text: turno.text_redacted,
            })),
            own,
          ),
    [detail.transcript, own],
  );
  if (detail.transcript.length === 0) {
    return <p className="text-fg-secondary">{t("inbox.transcript.empty")}</p>;
  }
  const turnos = detail.transcript.map((turno) => ({
    ...turno,
    shown: restaurados.get(turno.turn_id) ?? turno.text_redacted,
  }));
  return (
    <div className="flex flex-col gap-3">
      {turnos.some((turno) => isMasked(turno.shown)) ? (
        <p className="text-caption text-fg-secondary" data-testid="transcript-redacted-hint">
          {t("inbox.transcript.redacted_hint")}
        </p>
      ) : null}
      <ol className="flex flex-col gap-3" data-testid="case-transcript">
        {turnos.map((turno) => (
          <li key={turno.turn_id} className="flex flex-col gap-1">
            <p className="text-caption text-fg-secondary">
              {turno.speaker === "agent"
                ? t("inbox.transcript.speaker_agent")
                : t("inbox.transcript.speaker_insured")}
            </p>
            <p className="whitespace-pre-line">{turno.shown}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

/**
 * Las citas con el nombre de su parte en el idioma de la **pantalla** (C17, 2026-10-13).
 *
 * Estas pantallas no conversan, asi que el servidor no sabe en que idioma se leen: manda el
 * nombre original y el que tiene en el otro idioma. Si la pantalla esta en el idioma de la
 * poliza se deja el original; si esta en el otro, la tarjeta se rotula con el traducido
 * (`translated_part`, que es lo que la tarjeta ya prefiere en el chat). El texto de la
 * clausula no se toca. Sin traduccion en el corpus, queda el nombre original.
 */
function conRotuloDePantalla(
  citas: CoverageAnswerOut["citations"],
  locale: Locale,
): readonly (CoverageAnswerOut["citations"][number] & {
  readonly translated_part: string | null;
})[] {
  return citas.map((cita) => ({
    ...cita,
    translated_part: locale === cita.clause_language ? null : (cita.part_in_other_language ?? null),
  }));
}

/**
 * Las clausulas citadas, con su resultado y quien las emitio (bloque abierto).
 *
 * Reusa la cita expandible de U13, **la misma pieza y no una copia**: es el mismo
 * dato con la misma regla --el texto literal en su idioma, sin traducir-- y dos
 * implementaciones serian dos formas de mostrarlo que un dia difieren.
 *
 * BR2.6: cada clausula dice **quien la emitio**. En una agencia quien coloco la
 * poliza no es quien la expidio, y sin ese dato al lado las clausulas parecen de la
 * agencia.
 */
export function CitationList({
  answers,
  conversationLocale,
  own,
}: {
  readonly answers: readonly CoverageAnswerOut[];
  readonly conversationLocale: Locale;
  /** Lo que este navegador recuerda, si la pantalla es de quien hizo las preguntas. */
  readonly own?: OwnTexts | undefined;
}) {
  const { t, locale } = useLocale();
  const preguntas = useMemo(() => {
    const tapadas = answers.map((respuesta) => respuesta.question_redacted);
    return own === undefined ? tapadas : restoreAll(tapadas, own.visitor);
  }, [answers, own]);
  if (answers.length === 0) {
    return <p className="text-fg-secondary">{t("inbox.coverage.empty")}</p>;
  }
  return (
    <ol className="flex flex-col gap-4" data-testid="case-citations">
      {answers.map((respuesta, indice) => (
        <li key={respuesta.answer_id} className="flex flex-col gap-2">
          <p className="text-caption text-fg-secondary">{t("inbox.coverage.question")}</p>
          <p className="whitespace-pre-line">
            {preguntas.at(indice) ?? respuesta.question_redacted}
          </p>
          {/*
            La salida con su etiqueta propia: "sin clausula" y "no pude verificar"
            son dos cosas distintas y se leen distinto (BR2.5).
          */}
          <p data-testid={`coverage-outcome-${respuesta.answer_id}`}>
            <Tag tone={respuesta.outcome === "verified" ? "success" : "neutral"}>
              {coverageOutcomeLabel(respuesta.outcome)(t)}
            </Tag>
          </p>
          {withPositions(conRotuloDePantalla(respuesta.citations, locale)).map(
            ({ citation: cita, position }) => (
              <div key={cita.clause_id} className="flex flex-col gap-1">
                <Citation
                  citation={cita}
                  conversationLocale={conversationLocale}
                  position={position}
                />
                <p className="text-caption text-fg-secondary">
                  {t("inbox.coverage.issuer", { insurer: cita.issuer_label })}
                </p>
              </div>
            ),
          )}
        </li>
      ))}
    </ol>
  );
}

/**
 * Por que el caso paso a un ajustador, en una frase (bloque abierto, E3).
 *
 * El servidor manda la categoria y los identificadores de las reglas, no su explicacion:
 * la frase sale de la categoria y el identificador queda al final, pequeno, como
 * referencia. Sin categoria las reglas todavia no corrieron y no hay nada que decir, asi
 * que el bloque no se pinta.
 */
export function RuleBlock({ detail }: { readonly detail: CaseDetailOut }) {
  const { t } = useLocale();
  // Mientras la agente aun evalua el caso la categoria puede estar guardada y el caso no
  // haberse movido: decir «por que se cerro» o «por que paso a un ajustador» seria contar
  // un resultado que todavia no ocurrio.
  if (detail.rule_category === null || isUnderReview(detail.state)) {
    return null;
  }
  return (
    <OpenBlock
      title={
        detail.rule_category === "direct_close"
          ? t("inbox.block.rule_closed")
          : t("inbox.block.rule")
      }
      testId="block-rule"
    >
      <p>{ruleReasonLabel(detail.rule_category)(t)}</p>
      {detail.fired_rules.length === 0 ? null : (
        <p className="mt-2 text-caption text-fg-secondary" data-testid="rule-reference">
          {t("inbox.rule.reference", { rules: detail.fired_rules.join(", ") })}
        </p>
      )}
    </OpenBlock>
  );
}

/**
 * Que se reviso y que se encontro, en frases (bloque abierto, E3).
 *
 * Tres resultados y no dos: `controls_ok === null` significa que la revision completa
 * **no ha corrido**, y eso no se dice "sin hallazgos" --colapsarlos diria que se
 * comprobo algo que nadie comprobo--: el bloque no se pinta. Un codigo de hallazgo que
 * esta version no conoce se dice con la frase general y nunca crudo.
 */
export function ControlsBlock({ detail }: { readonly detail: CaseDetailOut }) {
  const { t } = useLocale();
  if (detail.controls_ok === null) {
    return null;
  }
  // Un control en falso sin codigo de hallazgo no deberia pasar, pero si pasa no se dice
  // que todo esta bien: se dice que hay un hallazgo, con la frase general.
  const codigos = detail.control_findings;
  const hayHallazgos = !detail.controls_ok || codigos.length > 0;
  return (
    <OpenBlock title={t("inbox.block.controls")} testId="block-controls">
      {hayHallazgos ? (
        <div className="flex flex-col gap-2">
          <p>{t("inbox.controls.some_findings")}</p>
          <ul className="flex flex-col gap-1" data-testid="control-findings">
            {(codigos.length > 0 ? codigos : [""]).map((codigo) => (
              <li key={codigo}>{findingLabel(codigo)(t)}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p>{t("inbox.controls.all_clear")}</p>
      )}
      <p className="mt-3 text-caption text-fg-secondary">{t("inbox.controls.reviewed")}</p>
    </OpenBlock>
  );
}

/**
 * Una direccion que se puede abrir en otra pestana: solo `https`. La manda el servidor, que ya
 * valida el host al arrancar; aqui se comprueba otra vez porque es lo ultimo antes de un
 * `href`, y un esquema distinto (`javascript:`) no tiene que llegar a pintarse nunca.
 */
export function isSafeExternalLink(direccion: string | null | undefined): direccion is string {
  return typeof direccion === "string" && /^https:\/\/[^\s]+$/.test(direccion);
}

/**
 * Cuanto tardo la respuesta y cuanto costo (bloque abierto, E3), y el enlace para ver en
 * Langfuse como trabajo la agente (2026-10-14).
 *
 * Solo lo medido: una fila sin dato no se pinta, y si no hay ninguno el bloque entero
 * tampoco ("No medido" en un cuadro no le dice nada a nadie). Un costo no medido nunca
 * se escribe como cero: un cero se suma despues como si fuera cierto, que es lo que el
 * tipo del servidor existe para impedir.
 *
 * **El enlace lo manda el servidor o no hay enlace.** `trace_url` llega solo por las dos
 * puertas con dueno (el personal y el visitante con el enlace de su caso) y nunca en un caso
 * de ejemplo; esta pieza no lo arma ni lo adivina. Se abre en otra pestana sin pasar el
 * origen (`noopener noreferrer`), y la nota dice con palabras que Langfuse es una herramienta
 * externa y que no muestra lo que se escribio.
 */
export function ResponseBlock({ detail }: { readonly detail: CaseDetailOut }) {
  const { t } = useLocale();
  const notaId = useId();
  const enlace = isSafeExternalLink(detail.trace_url) ? detail.trace_url : null;
  if (detail.trace_latency_ms === null && detail.trace_cost_usd === null && enlace === null) {
    return null;
  }
  return (
    <OpenBlock title={t("inbox.block.trace")} testId="block-trace">
      <dl className="flex flex-col gap-2">
        {detail.trace_latency_ms === null ? null : (
          <div>
            <dt className="text-caption text-fg-secondary">{t("trace.page.latency")}</dt>
            <dd className="font-mono text-caption" data-testid="trace-latency">
              {t("trace.page.milliseconds", { value: detail.trace_latency_ms })}
            </dd>
          </div>
        )}
        {detail.trace_cost_usd === null ? null : (
          <div>
            <dt className="text-caption text-fg-secondary">{t("trace.page.cost")}</dt>
            <dd className="font-mono text-caption" data-testid="trace-cost">
              {t("inbox.trace.cost", { value: detail.trace_cost_usd })}
            </dd>
          </div>
        )}
      </dl>
      {enlace === null ? null : (
        <div className="mt-3 flex flex-col gap-1" data-testid="trace-langfuse">
          <a
            href={enlace}
            target="_blank"
            rel="noopener noreferrer"
            aria-describedby={notaId}
            className="inline-flex min-h-11 items-center self-start text-link underline underline-offset-4"
            data-testid="trace-langfuse-link"
          >
            {t("inbox.trace.langfuse_link")}
          </a>
          <p id={notaId} className="text-caption text-fg-secondary">
            {t("inbox.trace.langfuse_note")}
          </p>
        </div>
      )}
    </OpenBlock>
  );
}

/**
 * Quien decidio, o que todavia nadie lo hizo (BR2.4, BR5.5).
 *
 * **Tres respuestas y ninguna en blanco.** `pending` dice "pendiente de decision",
 * porque un hueco se lee como un dato que se perdio; y en un caso cerrado sin
 * decisor --que hoy no existe-- dice que no hay decision registrada, que es la
 * verdad y no un hueco tampoco. El estado lo decide el servidor, con la misma pieza
 * que mide el caso de golden set de esta unidad: aqui no se vuelve a decidir.
 *
 * La del enlace de demostracion **no nombra a nadie de la aseguradora**: falsificar
 * eso seria falsificar la respuesta a "quien decidio", que es la pregunta que la
 * explicacion existe para contestar.
 *
 * **Un caso de ejemplo se lee sin credencial**, y el servidor manda el tipo de actor
 * (`staff`) sin su identificador: parecido a una credencial, no va en una pagina publica.
 * Entonces se dice que lo decidio un ajustador de la aseguradora, o --si lo cerro la
 * agencia, que no decide los casos-- que la agencia lo envio a la emisora. Cual de las dos
 * lo da la resolucion, que es lo que separa a las dos acciones del personal.
 */
export function decidedByMessage(detail: CaseDetailOut): Message {
  const { decided_by: estado, decided_by_kind: tipo, decided_by_id: quien } = detail.explanation;
  if (estado === "pending") {
    return (t) => t("inbox.explanation.pending");
  }
  if (tipo === "insured") {
    return (t) => t("inbox.explanation.by_visitor");
  }
  // El cierre directo lo aplica el sistema: nadie decidio, y un actor `system` no se
  // imprime ni se nombra como quien decidio (US1.17).
  if (isClosedByRules(detail)) {
    return (t) => t("inbox.explanation.by_rules");
  }
  if (quien === null) {
    if (tipo === "staff") {
      if (detail.resolution === "sent_to_insurer") {
        return (t) => t("inbox.explanation.by_agency");
      }
      return (t) => t("inbox.explanation.by_adjuster");
    }
    return (t) => t("inbox.explanation.nobody");
  }
  return (t) => t("inbox.explanation.by_staff", { who: quien });
}

/**
 * Cuando se decidio. La otra mitad de la pregunta, y tampoco queda en blanco.
 *
 * La hora se escribe en el formato del idioma de la pagina. Una marca ISO es
 * correcta y no se lee, y aqui lo que importa es que alguien la lea.
 */
export function decidedAtMessage(detail: CaseDetailOut, locale: Locale): Message {
  const cuando = detail.explanation.decided_at_iso;
  if (detail.explanation.decided_at === "pending") {
    return (t) => t("inbox.explanation.pending");
  }
  if (cuando === null) {
    return (t) => t("inbox.explanation.nobody");
  }
  return () => formatMoment(cuando, locale);
}

/**
 * Quien decidio y cuando, en un renglon. Sin decision todavia las dos mitades dicen lo
 * mismo --"Pendiente de decision"-- y se escribe una sola vez (visto el 2026-10-11:
 * salia dos veces seguidas).
 */
export function DecisionSummary({ detail }: { readonly detail: CaseDetailOut }) {
  const { t, locale } = useLocale();
  const quien = decidedByMessage(detail)(t);
  const cuando = decidedAtMessage(detail, locale)(t);
  return (
    <>
      <span>{quien}</span>
      {cuando === quien ? null : <span>{cuando}</span>}
    </>
  );
}

/** Un instante del cable, en el formato del idioma. Vale el crudo si no se pudo leer. */
export function formatMoment(iso: string, locale: Locale): string {
  const momento = new Date(iso);
  if (Number.isNaN(momento.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(
    momento,
  );
}

/** Solo la hora, para decir hasta cuando vale un enlace (BR5.3). */
export function formatTime(iso: string, locale: Locale): string {
  const momento = new Date(iso);
  if (Number.isNaN(momento.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(momento);
}
