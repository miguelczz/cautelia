// La vista de un caso con credencial (BR2.1 a BR2.6, BR3.1 a BR3.4, BR4.1 a BR4.6).
//
// **El encabezado se queda arriba al desplazar** y lleva junto el *por que llego* y
// el *que hago* (BR2.1, decision de Miguel del 2026-09-28). En el telefono es lo
// unico que garantiza que las acciones esten al alcance sin recorrer seis bloques;
// en pantalla ancha se ve casi igual que cualquier encabezado, asi que la diferencia
// se juega entera en el movil. La alternativa --una barra de accion fija abajo-- se
// descarto porque deja ver el boton sin ver el motivo, y el criterio los nombra en
// la misma frase.
//
// **Tres bloques abiertos y tres plegados, y cada plegado con su resultado en el
// titular** (BR2.2). Plegar oculta el detalle, nunca el dato.
//
// **Quien decidio y cuando se ven siempre**, y en un caso sin decidir dicen
// "pendiente de decision" (BR2.4). Un campo vacio se lee como un dato que se perdio.
//
// **Nada se decide dos veces.** Las acciones disponibles, si se puede corregir un
// campo y el estado de la explicacion llegan resueltos del servidor. Esta pantalla no
// se pregunta si la aseguradora es una agencia ni si el caso esta cerrado: hacerlo
// seria escribir esas reglas por segunda vez, en otro lenguaje, y el dia que una
// cambie la otra seguiria diciendo lo de antes.

import { useCallback, useEffect, useState } from "react";

import {
  annotateTriage,
  caseDetail,
  correctField,
  decideCase,
  openInboxStream,
  type CaseDetailOut,
  type InboxAction,
  type TriageNoteIn,
} from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { useAnnouncer } from "../../shared/ui/announcer";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { DETAIL_TITLE } from "../../shared/ui/page-layout";
import { Tag } from "../../shared/ui/tag";
import { PageSkeleton } from "../../shared/ui/page-skeletons";
import { DecisionForm } from "./decision-form";
import {
  CitationList,
  ControlsBlock,
  decidedAtMessage,
  decidedByMessage,
  FieldCompleteness,
  OpenBlock,
  ResponseBlock,
  RuleBlock,
  TranscriptView,
} from "./evidence-blocks";
import { FieldCorrection } from "./field-correction";
import { parseEvent, touchesCase } from "./inbox-events";
import {
  caseReasonLabel,
  isClosedByRules,
  isUnderReview,
  recordTypeLabel,
  resolutionLabel,
  reviewHint,
  ruleCategoryLabel,
  stateLabel,
} from "./inbox-labels";
import { TriageNoteBlock } from "./triage-note";

/**
 * La clave de idempotencia de una escritura.
 *
 * Una por intento y no una por caso: dos correcciones distintas del mismo campo son
 * dos escrituras legitimas, y compartir clave haria que la segunda devolviera el
 * recibo de la primera sin escribir nada. Lo que la clave evita es el **doble envio
 * del mismo intento**, que es lo que pasa al pulsar dos veces.
 */
function claveDeIntento(prefix: string): string {
  return `${prefix}-${String(Date.now())}-${Math.random().toString(36).slice(2, 10)}`;
}

export interface CaseDetailPageProps {
  readonly tenantId: string;
  readonly caseId: string;
  /** Como volver a la cola. */
  readonly queueHref: string;
  /** Solo para las pruebas: sin esto, el flujo real del navegador. */
  readonly openStream?: (tenantId: string) => EventSource;
}

export function CaseDetailPage({ tenantId, caseId, queueHref, openStream }: CaseDetailPageProps) {
  const { t, locale } = useLocale();
  const { announce } = useAnnouncer();
  const [caso, setCaso] = useState<CaseDetailOut | null>(null);
  const [problema, setProblema] = useState<ProblemView | null>(null);
  const [cargando, setCargando] = useState(true);
  // Si lo ultimo que hizo quien decide fue guardar lo que anoto para las reglas. Vive aqui y
  // no en el formulario porque el formulario se vuelve a montar cuando lo anotado cambia, y el
  // aviso tiene que sobrevivir a eso; se apaga en cuanto se toca un control.
  const [anotacionGuardada, setAnotacionGuardada] = useState(false);

  // La consulta vive **dentro** del efecto y quien quiere repetirla sube este
  // contador: un aviso en vivo, una decision registrada, una correccion guardada. Es
  // lo que evita un `setState` sincrono en el cuerpo del efecto --que dispara
  // renders en cascada-- sin renunciar a volver a pedir, y es la misma forma que uso
  // la pagina de traza de U13.
  const [recarga, setRecarga] = useState(0);
  const recargar = useCallback(() => {
    setRecarga((previa) => previa + 1);
  }, []);

  useEffect(() => {
    let vigente = true;
    const pedir = async (): Promise<void> => {
      const resultado = await caseDetail(tenantId, caseId);
      if (!vigente) {
        return;
      }
      setCargando(false);
      if (!resultado.ok) {
        setProblema(resultado.problem);
        setCaso(null);
        return;
      }
      setProblema(null);
      setCaso(resultado.value);
    };
    void pedir();
    return () => {
      vigente = false;
    };
    // `recarga` esta a proposito: subirlo es la forma de volver a pedir.
  }, [tenantId, caseId, recarga]);

  // BR6.1: la vista abierta se actualiza sola cuando su caso cambia. Se vuelve a
  // pedir **solo su caso** y no la cola: es una consulta, y el aviso no trae los seis
  // bloques.
  useEffect(() => {
    const flujo = (openStream ?? openInboxStream)(tenantId);
    flujo.onmessage = (evento: MessageEvent<string>) => {
      const aviso = parseEvent(evento.data);
      if (aviso !== null && touchesCase(aviso, caseId)) {
        recargar();
      }
    };
    return () => {
      flujo.close();
    };
  }, [tenantId, caseId, openStream, recargar]);

  if (cargando) {
    return <PageSkeleton kind="case" />;
  }

  if (caso === null) {
    // Un caso de otra aseguradora y uno que no existe responden igual, y esta
    // pantalla no los distingue tampoco: una frase distinta aqui desharia lo que el
    // servidor cuida, porque confirmaria que ese caso existe.
    return (
      <main className="mx-auto flex w-full max-w-content flex-col gap-4 px-4 py-6">
        <h1 className={DETAIL_TITLE}>{t("inbox.case.not_found")}</h1>
        <p className="text-small text-fg-secondary" data-testid="staff-note">
          {t("inbox.staff_note")}
        </p>
        {problema === null ? null : <p>{problema.message(t)}</p>}
        <Button asChild variant="primary">
          <a href={queueHref}>{t("inbox.case.back")}</a>
        </Button>
      </main>
    );
  }

  const decidir = async (accion: InboxAction, comentario: string): Promise<ProblemView | null> => {
    const resultado = await decideCase(tenantId, caseId, accion, comentario, claveDeIntento("dec"));
    if (!resultado.ok) {
      return resultado.problem;
    }
    announce(t("inbox.decision.recorded"));
    recargar();
    return null;
  };

  const corregir = async (clave: string, valor: string): Promise<ProblemView | null> => {
    const resultado = await correctField(tenantId, caseId, clave, valor, claveDeIntento("fix"));
    if (!resultado.ok) {
      return resultado.problem;
    }
    announce(t("inbox.correction.saved"));
    recargar();
    return null;
  };

  // Anotar para las reglas guarda lo anotado y vuelve a evaluar el caso; la pagina se
  // vuelve a leer para mostrar la evaluacion nueva en el bloque de las reglas.
  const anotar = async (nota: TriageNoteIn): Promise<ProblemView | null> => {
    const resultado = await annotateTriage(tenantId, caseId, nota, claveDeIntento("note"));
    if (!resultado.ok) {
      setAnotacionGuardada(false);
      return resultado.problem;
    }
    setAnotacionGuardada(true);
    announce(t("inbox.triage.saved"));
    recargar();
    return null;
  };

  return (
    <main
      className="mx-auto flex w-full max-w-content flex-col gap-4 px-4 pb-6"
      data-testid="inbox-case"
    >
      {/*
        El encabezado pegajoso (BR2.1): motivo, categoria, completitud y las acciones
        **juntos**, y arriba al desplazar. `z-10` lo pone por encima de los bloques y
        no del marco, y el `top-0` es relativo al desplazamiento de la pagina.
      */}
      <header
        data-testid="case-header"
        className="sticky top-0 z-10 -mx-4 flex flex-col gap-3 border-b border-hairline bg-page px-4 py-4"
      >
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 className={DETAIL_TITLE}>
            {t("inbox.case.title", { case_number: caso.case_number })}
          </h1>
          {/*
            Un boton y no un enlace suelto: el primitivo garantiza 44 x 44, y un
            enlace de texto medía 81 x 17. Lo encontro el arnes, que mide los
            objetivos tactiles a 360 de ancho; sigue siendo un enlace por dentro.
          */}
          <Button asChild variant="ghost" size="compact">
            <a href={queueHref}>{t("inbox.case.back")}</a>
          </Button>
        </div>
        <p className="text-small text-fg-secondary" data-testid="staff-note">
          {t("inbox.staff_note")}
        </p>

        <dl className="flex flex-wrap gap-x-6 gap-y-2">
          <div>
            <dt className="text-caption text-fg-secondary">{t("inbox.case.reason")}</dt>
            <dd data-testid="case-reason">{caseReasonLabel(caso)(t)}</dd>
          </div>
          <div>
            <dt className="text-caption text-fg-secondary">{t("inbox.case.category")}</dt>
            <dd className="flex flex-wrap items-center gap-1">
              <Tag>{recordTypeLabel(caso.record_type)(t)}</Tag>
              <Tag>{stateLabel(caso.state)(t)}</Tag>
              {caso.rule_category === null ? (
                <span className="text-caption text-fg-secondary">
                  {t("inbox.case.no_category")}
                </span>
              ) : (
                <Tag tone="brand">{ruleCategoryLabel(caso.rule_category)(t)}</Tag>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-caption text-fg-secondary">{t("inbox.case.completeness")}</dt>
            <dd className="font-mono" data-testid="case-completeness">
              {t("inbox.completeness", {
                complete: caso.completeness_complete,
                total: caso.completeness_total,
              })}
            </dd>
          </div>
          {/*
            BR2.4: quien decidio y cuando, **siempre a la vista**, y "pendiente de
            decision" donde todavia no hay decision.
          */}
          <div>
            <dt className="text-caption text-fg-secondary">{t("inbox.explanation.title")}</dt>
            {/*
              Las dos mitades en dos elementos y no en una sola frase: una prueba que
              mire el texto junto no puede distinguir cual de las dos hablo, y con la
              frase junta se pudo vaciar "pendiente de decision" de una de ellas sin
              que se cayera ninguna prueba. Lo encontro la revision de esta tanda.
            */}
            <dd className="flex flex-wrap gap-x-2">
              <span data-testid="case-decided-by">{decidedByMessage(caso)(t)}</span>
              <span data-testid="case-decided-at">{decidedAtMessage(caso, locale)(t)}</span>
            </dd>
          </div>
          {caso.resolution === null ? null : (
            <div>
              <dt className="text-caption text-fg-secondary">{t("inbox.case.resolution")}</dt>
              <dd data-testid="case-resolution">{resolutionLabel(caso.resolution)(t)}</dd>
            </div>
          )}
        </dl>

        {/*
          Las acciones, al lado del motivo. Cuando no hay ninguna se dice **por que**,
          y la razon sale del estado que el servidor ya manda: no es una segunda
          definicion de la regla, es la etiqueta del estado que la produjo.
        */}
        {caso.available_actions.length > 0 ? (
          <>
            {/* Un caso que la agente aun evalua se puede tomar, y tomarlo cuesta algo:
                las reglas ya no lo cierran solas. Se dice antes de ofrecer los botones. */}
            {isUnderReview(caso.state) ? (
              <p className="text-caption text-fg-secondary" data-testid="case-takeover-note">
                {t("inbox.decision.takeover_note")}
              </p>
            ) : null}
            <DecisionForm actions={caso.available_actions} onSubmit={decidir} idPrefix="staff" />
          </>
        ) : (
          <p className="text-caption text-fg-secondary" data-testid="case-no-actions">
            {caso.state === "awaiting_insured"
              ? t("inbox.decision.none_awaiting")
              : isClosedByRules(caso)
                ? t("inbox.decision.none_closed_by_rules")
                : caso.state === "closed"
                  ? t("inbox.decision.none_closed")
                  : (reviewHint(caso.state)?.(t) ?? t("inbox.decision.none_in_conversation"))}
          </p>
        )}
      </header>

      {problema === null ? null : (
        <InlineAlert tone="danger" role="alert" data-testid="case-problem">
          {problema.message(t)}
        </InlineAlert>
      )}

      {/* Los tres bloques abiertos. */}
      <OpenBlock title={t("inbox.block.fields")} testId="block-fields">
        {caso.state === "awaiting_insured" ? (
          <p className="mb-3 text-caption text-fg-secondary">{t("inbox.fields.awaiting")}</p>
        ) : null}
        {caso.can_correct_fields ? null : (
          <p className="mb-3 text-caption text-fg-secondary">{t("inbox.correction.closed")}</p>
        )}
        <FieldCompleteness
          fields={caso.fields}
          {...(caso.can_correct_fields
            ? {
                correctionFor: (campo) => (
                  <FieldCorrection key={campo.field_key} field={campo} onSave={corregir} />
                ),
              }
            : {})}
        />
      </OpenBlock>

      <OpenBlock title={t("inbox.block.transcript")} testId="block-transcript">
        <TranscriptView detail={caso} />
      </OpenBlock>

      <OpenBlock title={t("inbox.block.citations")} testId="block-citations">
        <CitationList answers={caso.coverage_answers} conversationLocale={caso.language} />
      </OpenBlock>

      {/* Lo que el ajustador anota para las reglas va justo antes del bloque que dice que
          decidieron: al guardar, ese bloque se actualiza con la evaluacion nueva. La clave
          vuelve a montar el formulario cuando lo anotado cambia por otro lado. */}
      <TriageNoteBlock
        key={JSON.stringify(caso.triage_note ?? null)}
        note={caso.triage_note}
        canAnnotate={caso.can_annotate_triage === true}
        onSave={anotar}
        saved={anotacionGuardada}
        onEdit={() => {
          setAnotacionGuardada(false);
        }}
      />

      {/* Los tres ultimos dicen en una frase lo que tienen, y el que no tiene nada que
          decir no se pinta (E3, 2026-10-12). Aqui la conversacion sigue tapada: quien
          entra con credencial de personal no es quien la escribio. */}
      <RuleBlock detail={caso} />
      <ControlsBlock detail={caso} />
      <ResponseBlock detail={caso} />
    </main>
  );
}
