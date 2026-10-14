// El resumen de una respuesta, sin credencial (BR4.3, BR4.4; AC2.3.2, AC2.3.3).
//
// **Lo que no existe y lo que es de otro se ven igual.** El servidor responde lo
// mismo a las tres causas --no existe, es de otra conversacion, es de otra
// aseguradora-- y esta pantalla no las distingue tampoco: una frase distinta aqui
// desharia lo que el servidor cuida, porque confirmaria que esa traza existe.
//
// **"Se esta registrando" no es "no hay nada".** Son dos hechos distintos y se
// dicen distinto; mientras se registra, la pagina vuelve a preguntar sola.

import { useCallback, useEffect, useState } from "react";

import { traceSummary, type TraceView } from "../../shared/api-client/chat";
import { useLocale } from "../../shared/i18n/locale-provider";
import type { Translate } from "../../shared/i18n/translate";
import { PageSkeleton } from "../../shared/ui/page-skeletons";
import { DETAIL_TITLE } from "../../shared/ui/page-layout";

/**
 * El paso por lo que hizo, no por su nombre interno (fase 3, 2026-10-08). Uno que esta
 * tabla no conoce se muestra tal cual: inventarle una frase seria peor.
 */
export function nodeLabel(node: string, t: Translate): string {
  switch (node) {
    case "intake":
      return t("trace.node.intake");
    case "policy_verification":
      return t("trace.node.policy_verification");
    case "decision":
      return t("trace.node.decision");
    case "compliance":
      return t("trace.node.compliance");
    default:
      return node;
  }
}

/** Cada cuanto vuelve a preguntar mientras el rastro se registra (BR4.4). */
export const REFRESH_MS = 3000;

export interface TracePageProps {
  readonly tenantId: string;
  readonly traceId: string;
  /** Solo para las pruebas: sin esto, la consulta real. */
  readonly load?: (tenantId: string, traceId: string) => Promise<TraceView | null>;
}

type Estado =
  { readonly cargando: true } | { readonly cargando: false; readonly vista: TraceView | null };

export function TracePage({ tenantId, traceId, load }: TracePageProps) {
  const { t } = useLocale();
  const [estado, setEstado] = useState<Estado>({ cargando: true });
  const consultar = useCallback(
    () => (load ?? traceSummary)(tenantId, traceId),
    [load, tenantId, traceId],
  );

  useEffect(() => {
    let vigente = true;
    let temporizador: ReturnType<typeof setTimeout> | undefined;

    const preguntar = async (): Promise<void> => {
      const vista = await consultar();
      if (!vigente) {
        return;
      }
      setEstado({ cargando: false, vista });
      // Solo mientras se registra: una traza lista o perdida ya no cambia, y
      // seguir preguntando seria trabajo que nadie mira.
      if (vista?.status === "recording") {
        temporizador = setTimeout(() => void preguntar(), REFRESH_MS);
      }
    };

    void preguntar();
    return () => {
      vigente = false;
      if (temporizador !== undefined) {
        clearTimeout(temporizador);
      }
    };
  }, [consultar]);

  if (estado.cargando) {
    return <PageSkeleton kind="generic" />;
  }

  const vista = estado.vista;
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-4 px-4 py-6">
      <a
        href={`/t/${encodeURIComponent(tenantId)}/chat`}
        className="inline-flex min-h-11 items-center self-start text-link underline underline-offset-4"
      >
        {t("trace.page.back")}
      </a>
      <h1 className={DETAIL_TITLE}>{t("trace.page.title")}</h1>
      {vista === null ? (
        <p>{t("trace.page.nothing_here")}</p>
      ) : vista.status === "recording" ? (
        <p role="status">
          {t("trace.summary.recording")} {t("trace.page.recording_hint")}
        </p>
      ) : (
        <dl className="flex flex-col gap-3">
          <div>
            <dt className="text-caption text-fg-secondary">{t("trace.page.nodes")}</dt>
            <dd>
              <ol className="flex flex-col gap-1">
                {vista.nodes.map((nodo) => (
                  <li key={nodo.node} className="text-caption">
                    {nodeLabel(nodo.node, t)} ·{" "}
                    {t("trace.page.milliseconds", { value: nodo.duration_ms })}
                  </li>
                ))}
              </ol>
            </dd>
          </div>
          <div>
            <dt className="text-caption text-fg-secondary">{t("trace.page.clauses")}</dt>
            <dd className="text-caption">
              {vista.clauses_retrieved} / {vista.clauses_verified}
            </dd>
          </div>
          <div>
            <dt className="text-caption text-fg-secondary">{t("trace.page.latency")}</dt>
            <dd className="text-caption">
              {vista.latency_ms === null
                ? t("trace.page.not_measured")
                : t("trace.page.milliseconds", { value: vista.latency_ms })}
            </dd>
          </div>
          <div>
            <dt className="text-caption text-fg-secondary">{t("trace.page.cost")}</dt>
            {/*
              Sin precio se dice "no medido" y **nunca cero**: un cero se suma
              despues como si fuera cierto, que es lo que el tipo del servidor
              existe para impedir.
            */}
            <dd className="text-caption">
              {vista.cost_usd === null ? t("trace.page.not_measured") : `${vista.cost_usd} USD`}
            </dd>
          </div>
        </dl>
      )}
    </main>
  );
}
