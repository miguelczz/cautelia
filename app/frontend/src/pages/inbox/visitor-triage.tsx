// La version guiada de «anotar para las reglas», para el visitante que hace de ajustador
// sobre su propio caso (2026-10-13).
//
// **No es el formulario del personal con un interruptor** (`triage-note.tsx`): quien lo usa
// «no sabe ni lo que esta haciendo», asi que cada dato lleva su ayuda y el monto, que el
// personal escribe en miles, aqui se escribe en pesos. Comparten las funciones puras --leer el
// monto, pasar un selector a si/no/sin anotar-- y nada mas: dos juegos de etiquetas sobre un
// solo formulario es la forma segura de que un dia se cruce uno, y el de la persona que
// reporto no puede decir bandeja, cola ni triaje (U-07).
//
// **Lo que se pinta lo decide el servidor.** `can_annotate_triage` dice si se ofrece anotar
// (estado del caso, tope de anotaciones, nota del personal) y `triage_amount_steps` trae los
// montos desde los que cambian las reglas de **esta** aseguradora: ninguna cifra esta
// escrita aqui. Los tres botones de ejemplo salen de esos umbrales.
//
// **El monto va en pesos, la cifra del motor en miles.** Se redondea al millar mas cercano y
// debajo se lee como se va a anotar, con el mismo formateador de las pantallas de polizas:
// un cero de mas se nota antes de guardar.
//
// **«No lo he revisado» y «No» son dos respuestas distintas.** Una regla no dispara con un
// dato sin anotar y un «No» afirma que se comprobo; por eso cada selector tiene las tres
// opciones y el monto vacio se manda como `null`. Se manda siempre el estado completo.
//
// **Lo escrito no se pierde.** Ni cuando el servidor rechaza el guardado ni cuando el tope se
// alcanza: los datos siguen donde estan, y si el servidor deja de ofrecer anotar la pantalla
// pasa a leerlos y conserva el aviso.

import { useState } from "react";

import type { TriageNoteIn, TriageNoteView } from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { Input } from "../../shared/ui/input";
import { Select } from "../../shared/ui/select";
import { formatPesos, PESOS_POR_UNIDAD } from "../policies/policies-page";
import { ruleReasonLabel } from "./inbox-labels";
import { StepHeading } from "./step-heading";
import { answerOf, parseAmount, valueOf, type Answer } from "./triage-note";

/** Lo que las reglas dijeron con lo que se acaba de guardar. */
export interface TriageOutcome {
  /** La categoria de la evaluacion vigente, o `null` si el caso no tiene ninguna. */
  readonly ruleCategory: string | null;
  readonly firedRules: readonly string[];
  /** Falso cuando se guardo lo que ya estaba: no se escribio nada ni se evaluo otra vez. */
  readonly changed: boolean;
}

export type TriageSaveResult =
  | { readonly ok: true; readonly outcome: TriageOutcome }
  | { readonly ok: false; readonly problem: ProblemView };

/** Pesos a la cifra interna del motor: miles, redondeada al millar mas cercano. */
export function internalAmount(pesos: number): number {
  return Math.round(pesos / PESOS_POR_UNIDAD);
}

/**
 * Los montos de ejemplo, en la cifra interna: uno por debajo del primer umbral (la mitad), uno
 * entre el primero y el ultimo (el punto medio; no con un solo umbral) y uno por encima del
 * ultimo (el doble). Sin umbrales no hay ejemplos: nada que ilustrar.
 */
export function exampleAmounts(steps: readonly number[]): readonly number[] {
  const primero = steps[0];
  const ultimo = steps[steps.length - 1];
  if (primero === undefined || ultimo === undefined) {
    return [];
  }
  const ejemplos = [Math.floor(primero / 2)];
  if (steps.length >= 2) {
    ejemplos.push(Math.round((primero + ultimo) / 2));
  }
  ejemplos.push(ultimo * 2);
  return Array.from(new Set(ejemplos));
}

export interface VisitorTriageBlockProps {
  /** Lo que el visitante anoto, o `null`: el servidor no manda nunca la nota del personal. */
  readonly note: TriageNoteView | null | undefined;
  /** Si el servidor ofrece anotar ahora. */
  readonly canAnnotate: boolean;
  /** Los montos desde los que cambian las reglas, en la cifra interna. Llegan con `canAnnotate`. */
  readonly amountSteps: readonly number[] | undefined;
  /** Lo que la pantalla hace al guardar: lo manda y vuelve a leer el caso. */
  readonly onSave: (note: TriageNoteIn) => Promise<TriageSaveResult>;
  /**
   * El numero de paso de su titulo, cuando el panel del ajustador tiene mas de uno. Sin el, el
   * titulo se dibuja sin marca. El bloque es un paso del panel: su titulo es de nivel 3.
   */
  readonly step?: number | undefined;
}

const ID_MONTO = "visitor-triage-amount";
const ID_COBERTURA = "visitor-triage-coverage";
const ID_FRAUDE = "visitor-triage-fraud";

export function VisitorTriageBlock({
  note,
  canAnnotate,
  amountSteps,
  onSave,
  step,
}: VisitorTriageBlockProps) {
  const { t, locale } = useLocale();
  const [monto, setMonto] = useState(
    note?.claim_amount == null ? "" : String(note.claim_amount * PESOS_POR_UNIDAD),
  );
  const [cobertura, setCobertura] = useState<Answer>(answerOf(note?.coverage_disputed));
  const [fraude, setFraude] = useState<Answer>(answerOf(note?.fraud_suspected));
  const [montoInvalido, setMontoInvalido] = useState(false);
  const [problema, setProblema] = useState<ProblemView | null>(null);
  const [resultado, setResultado] = useState<TriageOutcome | null>(null);
  const [enviando, setEnviando] = useState(false);

  const respuesta = (valor: boolean | null | undefined): string => {
    const quien = answerOf(valor);
    if (quien === "yes") {
      return t("inbox.triage.answer_yes");
    }
    return quien === "no" ? t("inbox.triage.answer_no") : t("visitor.triage.unset");
  };

  if (!canAnnotate) {
    // Sin nada que mostrar ni que avisar, el bloque no existe: un servidor que dice que no se
    // puede anotar y un caso sin nota no tienen nada que contarle a quien lo lee.
    if ((note === null || note === undefined) && problema === null) {
      return null;
    }
    return (
      <section
        aria-labelledby="visitor-triage-title"
        className="flex flex-col gap-3"
        data-testid="visitor-triage"
      >
        <StepHeading id="visitor-triage-title" step={step}>
          {t("visitor.triage.title")}
        </StepHeading>
        {note === null || note === undefined ? null : (
          <dl className="flex flex-col gap-2" data-testid="visitor-triage-readonly">
            <div>
              <dt className="text-caption text-fg-secondary">{t("visitor.triage.amount_label")}</dt>
              <dd data-testid="visitor-triage-amount-value">
                {note.claim_amount === null
                  ? t("visitor.triage.unset")
                  : formatPesos(note.claim_amount, locale)}
              </dd>
            </div>
            <div>
              <dt className="text-caption text-fg-secondary">
                {t("visitor.triage.coverage_label")}
              </dt>
              <dd data-testid="visitor-triage-coverage-value">
                {respuesta(note.coverage_disputed)}
              </dd>
            </div>
            <div>
              <dt className="text-caption text-fg-secondary">{t("visitor.triage.fraud_label")}</dt>
              <dd data-testid="visitor-triage-fraud-value">{respuesta(note.fraud_suspected)}</dd>
            </div>
          </dl>
        )}
        {problema === null ? null : (
          <InlineAlert tone="info" data-testid="visitor-triage-problem">
            {problema.message(t)}
          </InlineAlert>
        )}
      </section>
    );
  }

  const pasos = amountSteps ?? [];
  const primero = pasos[0];
  const ultimo = pasos[pasos.length - 1];
  const ayudaDelMonto =
    primero === undefined || ultimo === undefined
      ? t("visitor.triage.amount_help_none")
      : pasos.length === 1
        ? t("visitor.triage.amount_help_one", { first: formatPesos(primero, locale) })
        : t("visitor.triage.amount_help", {
            first: formatPesos(primero, locale),
            last: formatPesos(ultimo, locale),
          });
  const ejemplos = exampleAmounts(pasos);

  const leido = parseAmount(monto);

  const editado = (): void => {
    // Lo que se muestra de la vez anterior deja de ser verdad en cuanto algo cambia.
    setProblema(null);
    setResultado(null);
  };

  const guardar = async (): Promise<void> => {
    if (leido === null) {
      setMontoInvalido(true);
      return;
    }
    setMontoInvalido(false);
    setEnviando(true);
    const guardado = await onSave({
      claim_amount: leido.kind === "ok" ? internalAmount(leido.value) : null,
      coverage_disputed: valueOf(cobertura),
      fraud_suspected: valueOf(fraude),
    });
    setEnviando(false);
    // Lo escrito se queda donde esta, tambien al fallar.
    if (guardado.ok) {
      setProblema(null);
      setResultado(guardado.outcome);
    } else {
      setResultado(null);
      setProblema(guardado.problem);
    }
  };

  const idAyudaMonto = `${ID_MONTO}-help`;
  const idVistaPrevia = `${ID_MONTO}-preview`;
  const idErrorMonto = `${ID_MONTO}-error`;
  const idEjemplos = `${ID_MONTO}-examples`;
  const idAyudaCobertura = `${ID_COBERTURA}-help`;
  const idAyudaFraude = `${ID_FRAUDE}-help`;
  const idProblema = "visitor-triage-problem";
  const vistaPrevia = !montoInvalido && leido?.kind === "ok";
  const describeElMonto = [idAyudaMonto, vistaPrevia ? idVistaPrevia : null]
    .concat(montoInvalido ? [idErrorMonto] : [])
    .filter((id): id is string => id !== null)
    .join(" ");

  // Lo que las reglas dijeron, en una linea: que volvieron a evaluar (solo si algo cambio),
  // la frase de la categoria y la referencia a las reglas que dispararon.
  const lineaDelResultado =
    resultado === null
      ? ""
      : [
          resultado.changed ? t("visitor.triage.result") : null,
          resultado.ruleCategory === null ? null : ruleReasonLabel(resultado.ruleCategory)(t),
          resultado.firedRules.length === 0
            ? null
            : t("inbox.rule.reference", { rules: resultado.firedRules.join(", ") }),
        ]
          .filter((parte): parte is string => parte !== null)
          .join(" ");

  return (
    <section
      aria-labelledby="visitor-triage-title"
      className="flex flex-col gap-3"
      data-testid="visitor-triage"
    >
      <StepHeading id="visitor-triage-title" step={step}>
        {t("visitor.triage.title")}
      </StepHeading>
      <p className="text-caption text-fg-secondary">{t("visitor.triage.intro")}</p>

      <form
        className="flex flex-col gap-3"
        data-testid="visitor-triage-form"
        onSubmit={(evento) => {
          evento.preventDefault();
          void guardar();
        }}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor={ID_MONTO} className="text-caption text-fg-secondary">
            {t("visitor.triage.amount_label")}
          </label>
          <Input
            id={ID_MONTO}
            inputMode="numeric"
            autoComplete="off"
            value={monto}
            invalid={montoInvalido}
            aria-describedby={describeElMonto}
            onChange={(evento) => {
              setMonto(evento.target.value);
              setMontoInvalido(false);
              editado();
            }}
          />
          <p id={idAyudaMonto} className="text-caption text-fg-secondary">
            {ayudaDelMonto}
          </p>
          {ejemplos.length === 0 ? null : (
            <div
              className="flex flex-wrap items-center gap-2"
              role="group"
              aria-labelledby={idEjemplos}
              data-testid="visitor-triage-examples"
            >
              <span id={idEjemplos} className="text-caption text-fg-secondary">
                {t("visitor.triage.amount_examples")}
              </span>
              {ejemplos.map((ejemplo) => (
                <Button
                  key={ejemplo}
                  type="button"
                  variant="secondary"
                  size="compact"
                  onClick={() => {
                    setMonto(String(ejemplo * PESOS_POR_UNIDAD));
                    setMontoInvalido(false);
                    editado();
                  }}
                >
                  {formatPesos(ejemplo, locale)}
                </Button>
              ))}
            </div>
          )}
          {montoInvalido ? (
            <InlineAlert tone="danger" role="alert" id={idErrorMonto}>
              {t("visitor.triage.amount_invalid")}
            </InlineAlert>
          ) : leido?.kind === "ok" ? (
            <p
              id={idVistaPrevia}
              className="text-caption text-fg-secondary"
              data-testid="visitor-triage-amount-preview"
            >
              {t("visitor.triage.amount_preview", {
                amount: formatPesos(internalAmount(leido.value), locale),
              })}
            </p>
          ) : null}
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor={ID_COBERTURA} className="text-caption text-fg-secondary">
            {t("visitor.triage.coverage_label")}
          </label>
          <Select
            id={ID_COBERTURA}
            value={cobertura}
            aria-describedby={idAyudaCobertura}
            onChange={(evento) => {
              setCobertura(evento.target.value as Answer);
              editado();
            }}
          >
            <option value="unset">{t("visitor.triage.unset")}</option>
            <option value="yes">{t("inbox.triage.answer_yes")}</option>
            <option value="no">{t("inbox.triage.answer_no")}</option>
          </Select>
          <p id={idAyudaCobertura} className="text-caption text-fg-secondary">
            {t("visitor.triage.coverage_help")}
          </p>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor={ID_FRAUDE} className="text-caption text-fg-secondary">
            {t("visitor.triage.fraud_label")}
          </label>
          <Select
            id={ID_FRAUDE}
            value={fraude}
            aria-describedby={idAyudaFraude}
            onChange={(evento) => {
              setFraude(evento.target.value as Answer);
              editado();
            }}
          >
            <option value="unset">{t("visitor.triage.unset")}</option>
            <option value="yes">{t("inbox.triage.answer_yes")}</option>
            <option value="no">{t("inbox.triage.answer_no")}</option>
          </Select>
          <p id={idAyudaFraude} className="text-caption text-fg-secondary">
            {t("visitor.triage.fraud_help")}
          </p>
        </div>

        {problema === null ? null : (
          <InlineAlert tone="danger" role="alert" id={idProblema} data-testid={idProblema}>
            {problema.message(t)}
          </InlineAlert>
        )}

        <div className="flex flex-col gap-2">
          <div>
            <Button type="submit" variant="secondary" disabled={enviando}>
              {t("visitor.triage.save")}
            </Button>
          </div>
          {/* La region existe desde el principio: una que aparece ya con su texto no siempre
              se anuncia. */}
          <div role="status" data-testid="visitor-triage-result">
            {lineaDelResultado === "" ? null : <p className="text-body">{lineaDelResultado}</p>}
          </div>
        </div>
      </form>
    </section>
  );
}
