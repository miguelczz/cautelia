// El panel "Documentos que consulta Catalina" (fase 2, 2026-10-08).
//
// Una ventana con los documentos del corpus de una aseguradora: la lista a un lado y
// las clausulas del elegido al otro, con un buscador, que endoso modifica cada una y
// cuantas veces se cito en la ultima semana. Dice tambien lo que no cambia: los
// documentos no aprenden de las conversaciones.
//
// Es el `<dialog>` del navegador y no un componente nuevo: `showModal()` ya atrapa el
// foco, cierra con Escape y deja inerte lo de atras, sin agregar una dependencia.

import { BooksIcon } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";

import { toProblemView } from "../../shared/api-client/problems";
import {
  documentQueryOptions,
  documentsQueryOptions,
  type DocumentView,
} from "../../shared/api-client/policies";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Translate } from "../../shared/i18n/translate";
import { useAgentName } from "../../shared/site/agent-name";
import { Button } from "../../shared/ui/button";
import { cn } from "../../shared/ui/cn";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { Input } from "../../shared/ui/input";
import { PanelBodySkeleton } from "../../shared/ui/page-skeletons";
import { lockPageScroll } from "../../shared/ui/scroll-lock";

/** El nombre de un documento para quien lo lee, sin identificadores del corpus. */
export function documentName(documento: DocumentView, t: Translate): string {
  if (documento.kind === "jurisdiction") {
    return t("documents.kind_jurisdiction");
  }
  const endoso = /END-(\d+)$/.exec(documento.form_id);
  if (documento.kind === "endorsement" && endoso?.[1] !== undefined) {
    return t("documents.kind_endorsement", { number: endoso[1] });
  }
  return t("documents.kind_base", { year: documento.form_version.split(".")[0] ?? "" });
}

interface DocumentsButtonProps {
  readonly tenantId: string;
  readonly insurerName: string;
  readonly variant?: "secondary" | "compact";
}

/** El boton que abre el panel, con el panel dentro. */
export function DocumentsButton({
  tenantId,
  insurerName,
  variant = "secondary",
}: DocumentsButtonProps) {
  const { t } = useLocale();
  const ventana = useRef<HTMLDialogElement>(null);
  const [abierta, setAbierta] = useState(false);
  const agente = useAgentName(tenantId);

  useEffect(() => {
    const dialogo = ventana.current;
    if (dialogo === null) {
      return;
    }
    if (abierta && !dialogo.open) {
      dialogo.showModal();
    }
  }, [abierta]);

  // Mientras esta abierta, la pagina de atras no se mueve: ni con la rueda sobre el
  // fondo ni al llegar al final de la lista de clausulas. Se desplaza solo la ventana.
  useEffect(() => (abierta ? lockPageScroll() : undefined), [abierta]);

  return (
    <>
      {variant === "compact" ? (
        <Button
          type="button"
          variant="ghost"
          size="compact"
          className="shrink-0 gap-1.5 px-3 text-fg-secondary hover:text-fg tablet:px-4"
          aria-label={t("documents.open", { agent: agente })}
          onClick={() => {
            setAbierta(true);
          }}
        >
          <BooksIcon aria-hidden="true" focusable="false" size={18} className="text-tenant" />
          {/* En telefono, solo el icono: el nombre completo va en `aria-label`. */}
          <span className="sr-only tablet:not-sr-only">{t("documents.list_label")}</span>
        </Button>
      ) : (
        <Button
          variant="secondary"
          className="h-auto py-2 whitespace-normal"
          onClick={() => {
            setAbierta(true);
          }}
        >
          {t("documents.open", { agent: agente })}
        </Button>
      )}
      <dialog
        ref={ventana}
        aria-labelledby={`${tenantId}-documents-title`}
        onClose={() => {
          setAbierta(false);
        }}
        // La ventana se desplaza por dentro y no contagia el desplazamiento a la
        // pagina (`overscroll-contain`); el fondo la oscurece con el velo del sistema.
        className={cn(
          "m-auto w-[min(64rem,calc(100vw-2rem))] max-h-[calc(100dvh-2rem)] overflow-y-auto overscroll-contain",
          "rounded-surface border border-hairline bg-page p-0 text-fg shadow-raised backdrop:bg-scrim",
        )}
        data-testid="documents-dialog"
      >
        {abierta ? (
          <DocumentsPanel
            tenantId={tenantId}
            insurerName={insurerName}
            onClose={() => ventana.current?.close()}
          />
        ) : null}
      </dialog>
    </>
  );
}

function DocumentsPanel({
  tenantId,
  insurerName,
  onClose,
}: {
  readonly tenantId: string;
  readonly insurerName: string;
  readonly onClose: () => void;
}) {
  const { t } = useLocale();
  const agente = useAgentName(tenantId);
  const consulta = useQuery(documentsQueryOptions(tenantId));
  const [elegido, setElegido] = useState<string | null>(null);
  const documentos = consulta.data?.documents ?? [];
  const actual =
    documentos.find((d) => d.form_id === elegido) ??
    documentos.find((d) => d.kind === "base" && d.in_force) ??
    documentos[0];

  return (
    <div className="flex flex-col">
      {/* El titulo y "Cerrar" quedan arriba mientras la lista se desplaza: cerrar no
          obliga a volver al principio. */}
      <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-hairline bg-page px-4 py-3 tablet:px-6">
        <h2
          id={`${tenantId}-documents-title`}
          className="text-lead font-medium text-balance text-fg tablet:text-title"
        >
          {t("documents.title", { agent: agente })} · {insurerName}
        </h2>
        <Button variant="secondary" className="shrink-0" onClick={onClose}>
          {t("documents.close")}
        </Button>
      </header>
      <div className="flex flex-col gap-5 p-4 tablet:p-6">
        <div className="flex flex-col gap-2">
          <p className="max-w-[46rem] text-body text-fg-secondary">
            {t("documents.how", { agent: agente })}
          </p>
          <p className="max-w-[46rem] text-small text-fg-secondary">{t("documents.static")}</p>
        </div>
        {consulta.isPending ? (
          <PanelBodySkeleton label={t("documents.loading")} />
        ) : consulta.isError ? (
          <InlineAlert tone="danger">
            <p>{toProblemView(consulta.error).message(t)}</p>
          </InlineAlert>
        ) : (
          <div className="grid gap-5 tablet:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
            <nav aria-label={t("documents.list_label")}>
              <ul className="flex flex-col gap-1" data-testid="documents-list">
                {documentos.map((documento) => {
                  const esActual = documento.form_id === actual?.form_id;
                  return (
                    <li key={`${documento.form_id}-${documento.form_version}`}>
                      <button
                        type="button"
                        aria-pressed={esActual}
                        onClick={() => {
                          setElegido(documento.form_id);
                        }}
                        className={cn(
                          "flex min-h-11 w-full flex-col items-start gap-0.5 rounded-surface px-3 py-2 text-left",
                          "transition-colors duration-[160ms] ease-out hover:bg-surface",
                          esActual ? "bg-surface font-medium" : "",
                        )}
                      >
                        <span className="text-body text-fg">{documentName(documento, t)}</span>
                        <span className="text-caption text-fg-secondary">
                          {t("documents.clause_count", { count: documento.clause_count })}
                          {documento.in_force ? "" : ` · ${t("documents.not_in_force")}`}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </nav>
            {actual === undefined ? null : (
              <DocumentClauses key={actual.form_id} tenantId={tenantId} document={actual} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function DocumentClauses({
  tenantId,
  document: documento,
}: {
  readonly tenantId: string;
  readonly document: DocumentView;
}) {
  const { t, locale } = useLocale();
  const agente = useAgentName(tenantId);
  const consulta = useQuery(documentQueryOptions(tenantId, documento.form_id, locale));
  const [busqueda, setBusqueda] = useState("");
  // La traduccion de referencia por omision y el original a un clic (decision de
  // Miguel del 2026-10-08): lo que se lee tiene que estar en el idioma de la pantalla.
  const [original, setOriginal] = useState(false);
  const campo = useId();

  if (consulta.isPending) {
    return <PanelBodySkeleton label={t("documents.loading")} />;
  }
  if (consulta.isError) {
    return (
      <InlineAlert tone="danger">
        <p>{toProblemView(consulta.error).message(t)}</p>
      </InlineAlert>
    );
  }
  const termino = busqueda.trim().toLocaleLowerCase();
  const traducida = consulta.data.clauses.some((c) => c.translated_text != null);
  const textoDe = (c: { text: string; translated_text?: string | null }) =>
    original ? c.text : (c.translated_text ?? c.text);
  const parteDe = (c: { part: string; translated_part?: string | null }) =>
    original ? c.part : (c.translated_part ?? c.part);
  const clausulas = consulta.data.clauses.filter(
    (c) =>
      termino === "" ||
      textoDe(c).toLocaleLowerCase().includes(termino) ||
      parteDe(c).toLocaleLowerCase().includes(termino),
  );
  const nombreDeEndoso = (formId: string): string => {
    const numero = /END-(\d+)$/.exec(formId)?.[1];
    return numero === undefined ? formId : t("documents.kind_endorsement", { number: numero });
  };

  return (
    <section className="flex min-w-0 flex-col gap-3" data-testid="document-clauses">
      <h3 className="text-lead font-medium text-fg">{documentName(documento, t)}</h3>
      {documento.in_force ? null : (
        <p className="text-small text-fg-secondary">
          {t("documents.not_in_force_why", { agent: agente })}
        </p>
      )}
      {traducida ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="text-small text-fg-secondary">
            {original ? null : t("documents.translation_note")}
          </p>
          <button
            type="button"
            aria-pressed={original}
            onClick={() => {
              setOriginal((antes) => !antes);
            }}
            className="inline-flex min-h-11 items-center text-small underline underline-offset-4"
          >
            {original ? t("documents.show_translation") : t("documents.show_original")}
          </button>
        </div>
      ) : null}
      <div className="flex flex-col gap-1">
        <label htmlFor={campo} className="text-small text-fg-secondary">
          {t("documents.search_label")}
        </label>
        <Input
          id={campo}
          type="search"
          value={busqueda}
          onChange={(evento) => {
            setBusqueda(evento.target.value);
          }}
        />
      </div>
      {clausulas.length === 0 ? (
        <p className="text-body text-fg-secondary">{t("documents.no_match")}</p>
      ) : (
        <ol className="flex flex-col divide-y divide-hairline">
          {clausulas.map((clausula) => (
            <li key={clausula.clause_id} className="flex flex-col gap-1 py-3">
              <p className="text-caption text-fg-secondary">
                {parteDe(clausula)} · <span className="font-mono">{clausula.clause_key}</span>
              </p>
              <p
                className="text-body text-fg"
                lang={original || clausula.translated_text == null ? clausula.language : locale}
              >
                {textoDe(clausula)}
              </p>
              {clausula.amended_by.length === 0 ? null : (
                <p className="text-small text-fg-secondary">
                  {t("documents.amended_by", {
                    names: clausula.amended_by.map(nombreDeEndoso).join(", "),
                  })}
                </p>
              )}
              {clausula.cited_last_week === 0 ? null : (
                <p className="text-small text-fg-secondary">
                  {t("documents.cited", { count: clausula.cited_last_week })}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
