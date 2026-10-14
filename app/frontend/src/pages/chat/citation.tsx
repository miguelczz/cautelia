// La cita expandible (BR4.1, BR4.2, AC2.3.1, AC2.3.4).
//
// Tres cosas que la regla pide y que aqui se ven:
//
// - **El identificador y la version se muestran siempre**, cerrada o abierta: son
//   lo que deja ir a la poliza y buscar la misma clausula. Desde el 2026-10-08 van en
//   la linea pequena y el titulo dice "Ver la clausula exacta".
// - **El texto literal nunca se traduce ni se resume.** Cuando la clausula esta
//   escrita en otro idioma se dice cual es, se marca el fragmento con `lang` para
//   que un lector de pantalla lo lea con la voz correcta, y la explicacion --que
//   si esta en el idioma de la conversacion-- queda fuera del bloque literal. Lo
//   que la persona compara contra su poliza tiene que ser lo que su poliza dice.
// - **Si un cambio posterior afecta a la clausula se avisa**, porque el texto
//   completo puede nombrar un monto que ya no rige.
// - **Dos tarjetas no se rotulan igual** (2026-10-11). El corpus no trae un titulo por
//   clausula, asi que lo que las distingue es lo que si es verdad: una condicion
//   especial se llama por su numero, como en el panel de documentos, y las que
//   comparten rotulo en una misma respuesta se numeran ("clausula 1 de 2").

import { TreeStructureIcon } from "@phosphor-icons/react";
import { useState } from "react";

import { Button } from "../../shared/ui/button";

import {
  Disclosure,
  DisclosureCaret,
  DisclosureContent,
  DisclosureTrigger,
} from "../../shared/ui/disclosure";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Locale } from "../../shared/copy/copy-keys";
import type { Translate } from "../../shared/i18n/translate";

/** El nombre del idioma de la clausula en el de la conversacion, con la clave literal. */
function nombreDeIdioma(t: Translate, locale: Locale): string {
  return locale === "es" ? t("chat.citation.language_es") : t("chat.citation.language_en");
}

/**
 * Lo que esta pieza necesita de una cita: **los seis campos que dibuja**, y nada
 * mas.
 *
 * Antes pedia el evento de cita del chat entero, que lleva ademas la referencia de
 * traza. La bandeja (U14) reusa **esta misma pieza** --es el mismo dato con la
 * misma regla, y dos implementaciones serian dos formas de mostrarlo que un dia
 * difieren-- y su cita no trae esa referencia: la traza de un caso se enlaza desde
 * su propio bloque. Pedir lo que se usa deja entrar a las dos sin que ninguna
 * invente un campo.
 */
export interface CitationShape {
  readonly clause_id: string;
  readonly clause_version: string;
  readonly part: string;
  readonly text: string;
  readonly clause_language: Locale;
  readonly amount_deferred: boolean;
  /** La traduccion de referencia al idioma de la conversacion, si la hay. */
  readonly translated_text?: string | null;
  readonly translated_part?: string | null;
  /** De que condicion especial (endoso) es la clausula, si es de una. */
  readonly special_condition_number?: number | null;
}

/** Cual de las tarjetas de una respuesta que comparten rotulo es esta. */
export interface CitationPosition {
  readonly index: number;
  readonly total: number;
}

/** Lo que dos tarjetas tienen que tener distinto para no leerse igual. */
function labelKey(citation: CitationShape): string {
  return typeof citation.special_condition_number === "number"
    ? `special:${String(citation.special_condition_number)}`
    : `part:${citation.translated_part ?? citation.part}`;
}

/**
 * Cada cita con su posicion entre las que comparten rotulo en una misma respuesta, en el
 * orden en que llegaron. Una cita que no comparte rotulo con ninguna va sin posicion:
 * numerar lo que ya es unico seria ruido.
 */
export function withPositions<T extends CitationShape>(
  citations: readonly T[],
): readonly { readonly citation: T; readonly position: CitationPosition | undefined }[] {
  const totales = new Map<string, number>();
  for (const cita of citations) {
    totales.set(labelKey(cita), (totales.get(labelKey(cita)) ?? 0) + 1);
  }
  const vistas = new Map<string, number>();
  return citations.map((citation) => {
    const clave = labelKey(citation);
    const index = (vistas.get(clave) ?? 0) + 1;
    vistas.set(clave, index);
    const total = totales.get(clave) ?? 1;
    return { citation, position: total > 1 ? { index, total } : undefined };
  });
}

export interface CitationProps {
  readonly citation: CitationShape;
  /** El idioma de la conversacion, para saber si la clausula esta en otro. */
  readonly conversationLocale: Locale;
  /** Como enlazar al resumen de traza; sin traza, no se dibuja el enlace. */
  readonly traceHref?: string;
  /** Cuando otra tarjeta de la misma respuesta lleva el mismo rotulo, cual es esta. */
  readonly position?: CitationPosition | undefined;
}

export function Citation({ citation, conversationLocale, traceHref, position }: CitationProps) {
  const { t } = useLocale();
  const enOtroIdioma = citation.clause_language !== conversationLocale;
  const traduccion = citation.translated_text ?? null;
  const [conOriginal, setConOriginal] = useState(false);
  const idiomaOriginal = nombreDeIdioma(t, citation.clause_language);

  return (
    <div className="rounded-control border border-border bg-surface-alt p-3">
      <Disclosure>
        {/* Todo a la izquierda: el titulo con la flecha pegada a su lado y debajo la parte. */}
        <DisclosureTrigger caret={false} className="w-full justify-start px-0 text-left">
          <span className="flex flex-col items-start gap-0.5">
            <span className="flex items-center gap-2">
              <span>{t("chat.citation.expand")}</span>
              <DisclosureCaret />
            </span>
            <span className="text-caption text-fg-secondary">
              {/* Una condicion especial se llama como en el panel de documentos y no por la
                  "parte" que trae el corpus ("Endosos"). */}
              <span>
                {typeof citation.special_condition_number === "number"
                  ? t("chat.citation.special_condition", {
                      number: citation.special_condition_number,
                    })
                  : (citation.translated_part ?? citation.part)}
              </span>
              {position === undefined ? null : (
                <>
                  {" "}
                  <span aria-hidden="true">·</span>{" "}
                  <span>
                    {t("chat.citation.position", { index: position.index, total: position.total })}
                  </span>
                </>
              )}
            </span>
          </span>
        </DisclosureTrigger>
        <DisclosureContent className="mt-2 flex flex-col gap-2">
          {traduccion !== null ? (
            <>
              <p className="text-caption text-fg-secondary">
                {t("chat.citation.translation_note", { language: idiomaOriginal })}
              </p>
              <blockquote lang={conversationLocale} className="whitespace-pre-line">
                {traduccion}
              </blockquote>
              <button
                type="button"
                aria-expanded={conOriginal}
                onClick={() => {
                  setConOriginal((antes) => !antes);
                }}
                className="inline-flex min-h-11 items-center self-start text-caption underline underline-offset-4"
              >
                {conOriginal ? t("chat.citation.hide_original") : t("chat.citation.show_original")}
              </button>
              {conOriginal ? (
                <blockquote
                  lang={citation.clause_language}
                  className="whitespace-pre-line border-l-2 border-hairline pl-3 text-fg-secondary"
                >
                  {citation.text}
                </blockquote>
              ) : null}
            </>
          ) : (
            <>
              {enOtroIdioma ? (
                <p className="text-caption text-fg-secondary">
                  {t("chat.citation.other_language", { language: idiomaOriginal })}
                </p>
              ) : null}
              {/*
                `lang` con el idioma de la clausula y no con el de la pagina: es lo
                que hace que un lector de pantalla la lea con la voz de su idioma en
                vez de deletrear una frase en ingles con fonetica espanola.
              */}
              <blockquote lang={citation.clause_language} className="whitespace-pre-line">
                {citation.text}
              </blockquote>
            </>
          )}
          {citation.amount_deferred ? (
            <p className="text-caption text-fg-secondary">{t("chat.citation.amount_deferred")}</p>
          ) : null}
          {/* El codigo y la version, con la tarjeta abierta: con ellos se busca la misma
              clausula en la poliza (AC2.3.1, movido adentro por decision de Miguel). */}
          <p className="font-mono text-caption text-fg-secondary">
            {t("chat.citation.reference", {
              clause_id: citation.clause_id,
              version: citation.clause_version,
            })}
          </p>
          {traceHref === undefined ? null : (
            <Button asChild variant="ghost" size="compact" className="-ml-3 gap-1.5 self-start">
              <a href={traceHref}>
                <TreeStructureIcon
                  aria-hidden="true"
                  focusable="false"
                  size={16}
                  className="text-tenant"
                />
                {t("chat.citation.trace_link")}
              </a>
            </Button>
          )}
        </DisclosureContent>
      </Disclosure>
    </div>
  );
}
