// Lo que el ajustador anota para las reglas: monto estimado, cobertura en duda y sospecha de
// fraude (2026-10-13).
//
// **Es la pantalla de quien entro con credencial de personal.** El visitante que hace de
// ajustador tiene la suya, guiada (`visitor-triage.tsx`), que reutiliza de aqui las funciones
// puras. Lo que el servidor manda resuelto (`can_annotate_triage`) es lo que se dibuja: esta
// pantalla no vuelve a decidirlo.
//
// **«Sin anotar» y «No» son dos respuestas distintas, y la pantalla puede volver a dejar un
// dato sin anotar.** Una regla no dispara con un dato sin anotar y un «No» afirma que se
// comprobo; por eso cada selector tiene las tres opciones y el monto vacio se manda como
// `null`. Se manda siempre el estado completo de los tres.
//
// **El monto se escribe en miles de pesos**, que es la cifra con la que comparan las reglas
// y como el proyecto guarda los montos, y debajo se lee en pesos con el mismo formateador
// de las pantallas de polizas. Un cero de mas se nota antes de guardar.
//
// **La validacion es la del servidor.** Aqui solo se comprueba lo que hace falta para armar
// el cuerpo --que el monto sea un entero que JavaScript pueda representar--: un numero
// desmedido se volveria `null` al serializarse, y eso borraria lo anotado sin avisar. El
// rango lo comprueba el servidor y su mensaje sale del catalogo por su codigo.

import { useState } from "react";

import type { TriageNoteIn, TriageNoteView } from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { Input } from "../../shared/ui/input";
import { Select } from "../../shared/ui/select";
import { formatPesos } from "../policies/policies-page";
import { OpenBlock } from "./evidence-blocks";

export type Answer = "unset" | "yes" | "no";

export function answerOf(valor: boolean | null | undefined): Answer {
  if (valor === true) {
    return "yes";
  }
  return valor === false ? "no" : "unset";
}

export function valueOf(respuesta: Answer): boolean | null {
  if (respuesta === "yes") {
    return true;
  }
  return respuesta === "no" ? false : null;
}

/** El monto escrito: vacio es «sin anotar», un entero es un monto y todo lo demas, ninguno. */
export type Amount = { readonly kind: "empty" } | { readonly kind: "ok"; readonly value: number };

export function parseAmount(texto: string): Amount | null {
  const limpio = texto.trim();
  if (limpio === "") {
    return { kind: "empty" };
  }
  if (!/^\d+$/.test(limpio)) {
    return null;
  }
  const valor = Number(limpio);
  return Number.isSafeInteger(valor) ? { kind: "ok", value: valor } : null;
}

export interface TriageNoteBlockProps {
  /** Lo anotado, o `null` si nadie ha anotado nada. */
  readonly note: TriageNoteView | null | undefined;
  /** Si el servidor ofrece anotar ahora (rol, estado y tipo del caso). */
  readonly canAnnotate: boolean;
  /** Lo que la pantalla hace al guardar. Devuelve el error, si lo hubo. */
  readonly onSave: (note: TriageNoteIn) => Promise<ProblemView | null>;
  /** Cierto desde que se guardo y hasta que se vuelve a editar: lo guarda quien dibuja la pagina. */
  readonly saved: boolean;
  /** Se llama al cambiar cualquier control, para que el aviso de «guardado» se apague. */
  readonly onEdit: () => void;
}

export function TriageNoteBlock({
  note,
  canAnnotate,
  onSave,
  saved,
  onEdit,
}: TriageNoteBlockProps) {
  if (!canAnnotate) {
    return note === null || note === undefined ? null : <TriageNoteReadOnly note={note} />;
  }
  return <TriageNoteForm note={note} onSave={onSave} saved={saved} onEdit={onEdit} />;
}

function TriageNoteReadOnly({ note }: { readonly note: TriageNoteView }) {
  const { t, locale } = useLocale();
  const respuesta = (valor: boolean | null): string => {
    const quien = answerOf(valor);
    if (quien === "yes") {
      return t("inbox.triage.answer_yes");
    }
    return quien === "no" ? t("inbox.triage.answer_no") : t("inbox.triage.unset");
  };
  return (
    <OpenBlock title={t("inbox.triage.title")} testId="block-triage">
      <dl className="flex flex-col gap-2" data-testid="triage-readonly">
        <div>
          <dt className="text-caption text-fg-secondary">{t("inbox.triage.amount_label")}</dt>
          <dd data-testid="triage-amount-value">
            {note.claim_amount === null
              ? t("inbox.triage.unset")
              : formatPesos(note.claim_amount, locale)}
          </dd>
        </div>
        <div>
          <dt className="text-caption text-fg-secondary">{t("inbox.triage.coverage_label")}</dt>
          <dd data-testid="triage-coverage-value">{respuesta(note.coverage_disputed)}</dd>
        </div>
        <div>
          <dt className="text-caption text-fg-secondary">{t("inbox.triage.fraud_label")}</dt>
          <dd data-testid="triage-fraud-value">{respuesta(note.fraud_suspected)}</dd>
        </div>
      </dl>
      <p className="mt-3 text-caption text-fg-secondary">{t("inbox.triage.read_only")}</p>
    </OpenBlock>
  );
}

function TriageNoteForm({
  note,
  onSave,
  saved,
  onEdit,
}: Omit<TriageNoteBlockProps, "canAnnotate">) {
  const { t, locale } = useLocale();
  const [monto, setMonto] = useState(note?.claim_amount?.toString() ?? "");
  const [cobertura, setCobertura] = useState<Answer>(answerOf(note?.coverage_disputed));
  const [fraude, setFraude] = useState<Answer>(answerOf(note?.fraud_suspected));
  const [montoInvalido, setMontoInvalido] = useState(false);
  const [problema, setProblema] = useState<ProblemView | null>(null);
  const [enviando, setEnviando] = useState(false);

  const leido = parseAmount(monto);

  const guardar = async (): Promise<void> => {
    if (leido === null) {
      setMontoInvalido(true);
      return;
    }
    setMontoInvalido(false);
    setEnviando(true);
    const fallo = await onSave({
      claim_amount: leido.kind === "ok" ? leido.value : null,
      coverage_disputed: valueOf(cobertura),
      fraud_suspected: valueOf(fraude),
    });
    setEnviando(false);
    // Lo escrito se queda donde esta, tambien al fallar: perderlo por un rechazo del
    // servidor es la forma mas barata de que alguien vuelva a teclearlo mal.
    setProblema(fallo);
  };

  const editado = (): void => {
    setProblema(null);
    onEdit();
  };

  const idMonto = "triage-amount";
  const idCobertura = "triage-coverage";
  const idFraude = "triage-fraud";
  const idError = "triage-problem";

  return (
    <OpenBlock title={t("inbox.triage.title")} testId="block-triage">
      <form
        className="flex flex-col gap-3"
        data-testid="triage-form"
        onSubmit={(evento) => {
          evento.preventDefault();
          void guardar();
        }}
      >
        <p className="text-caption text-fg-secondary">{t("inbox.triage.intro")}</p>

        <div className="flex flex-col gap-1">
          <label htmlFor={idMonto} className="text-caption text-fg-secondary">
            {t("inbox.triage.amount_label")}
          </label>
          <Input
            id={idMonto}
            inputMode="numeric"
            autoComplete="off"
            value={monto}
            invalid={montoInvalido}
            {...(montoInvalido ? { "aria-describedby": `${idMonto}-error` } : {})}
            onChange={(evento) => {
              setMonto(evento.target.value);
              setMontoInvalido(false);
              editado();
            }}
          />
          {montoInvalido ? (
            <InlineAlert tone="danger" role="alert" id={`${idMonto}-error`}>
              {t("inbox.triage.amount_invalid")}
            </InlineAlert>
          ) : leido?.kind === "ok" ? (
            <p className="text-caption text-fg-secondary" data-testid="triage-amount-preview">
              {t("inbox.triage.amount_preview", { amount: formatPesos(leido.value, locale) })}
            </p>
          ) : null}
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor={idCobertura} className="text-caption text-fg-secondary">
            {t("inbox.triage.coverage_label")}
          </label>
          <Select
            id={idCobertura}
            value={cobertura}
            onChange={(evento) => {
              setCobertura(evento.target.value as Answer);
              editado();
            }}
          >
            <option value="unset">{t("inbox.triage.unset")}</option>
            <option value="yes">{t("inbox.triage.answer_yes")}</option>
            <option value="no">{t("inbox.triage.answer_no")}</option>
          </Select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor={idFraude} className="text-caption text-fg-secondary">
            {t("inbox.triage.fraud_label")}
          </label>
          <Select
            id={idFraude}
            value={fraude}
            onChange={(evento) => {
              setFraude(evento.target.value as Answer);
              editado();
            }}
          >
            <option value="unset">{t("inbox.triage.unset")}</option>
            <option value="yes">{t("inbox.triage.answer_yes")}</option>
            <option value="no">{t("inbox.triage.answer_no")}</option>
          </Select>
        </div>

        {problema === null ? null : (
          <InlineAlert tone="danger" role="alert" id={idError} data-testid="triage-problem">
            {problema.message(t)}
          </InlineAlert>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" variant="primary" disabled={enviando}>
            {t("inbox.triage.save")}
          </Button>
          {saved && problema === null ? (
            <span
              role="status"
              className="text-caption text-fg-secondary"
              data-testid="triage-saved"
            >
              {t("inbox.triage.saved")}
            </span>
          ) : null}
        </div>
      </form>
    </OpenBlock>
  );
}
