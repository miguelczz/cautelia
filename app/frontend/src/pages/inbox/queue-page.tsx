// La cola de casos de una aseguradora (BR1.1 a BR1.6, BR6.1).
//
// **El orden lo decide el servidor.** Prioridad primero y, dentro de cada
// prioridad, espera mas larga delante. Esta pantalla dibuja las filas en el orden
// en que llegaron y no reordena nada: dos personas mirando la misma cola tienen que
// ver lo mismo, y una pantalla que ordenara por su cuenta seria una segunda regla de
// orden escrita en otro sitio.
//
// **Los filtros viven en la direccion**, no en memoria. Una cola filtrada que se
// pierde al recargar obliga a volver a filtrar en cada vuelta y no se puede
// compartir con nadie.
//
// **Un filtro sin resultados lo dice y ofrece quitarlos** (BR1.3). Una lista vacia
// sin explicacion se lee como una bandeja vacia, que es lo contrario de lo que paso.
//
// **La aseguradora sale de la credencial.** El identificador de la direccion no
// elige nada: el servidor solo comprueba que coincida, y cuando no coincide responde
// como ante una credencial ilegible. Esta pantalla no intenta compensarlo.

import { useCallback, useEffect, useRef, useState } from "react";

import { listCases, openInboxStream, type QueueFilters } from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { useLocale } from "../../shared/i18n/locale-provider";
import { useAnnouncer } from "../../shared/ui/announcer";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { DETAIL_TITLE } from "../../shared/ui/page-layout";
import { RowsSkeleton } from "../../shared/ui/page-skeletons";
import { Select } from "../../shared/ui/select";
import { Tag } from "../../shared/ui/tag";
import {
  EMPTY_QUEUE,
  parseEvent,
  reduceQueue,
  withMore,
  withPage,
  type QueueState,
} from "./inbox-events";
import {
  channelLabel,
  priorityLabel,
  recordTypeLabel,
  stateLabel,
  waitedLabel,
} from "./inbox-labels";

/** Los valores de cada filtro, en el orden en que se ofrecen. */
const ESTADOS = ["verifying", "deciding", "derived", "awaiting_insured", "closed"] as const;
const CANALES = ["chat", "voice"] as const;
const IDIOMAS = ["es", "en"] as const;
const PRIORIDADES = ["high", "normal"] as const;

export interface CasesQueuePageProps {
  readonly tenantId: string;
  /** El nombre de la aseguradora, para el titulo. */
  readonly insurerLabel: string;
  /** Los filtros de la direccion. Quien los cambia es la ruta, no esta pantalla. */
  readonly filters: QueueFilters;
  readonly onFiltersChange: (filters: QueueFilters) => void;
  /** Como enlazar a un caso. */
  readonly caseHref: (caseId: string) => string;
  /** Solo para las pruebas: sin esto, el flujo real del navegador. */
  readonly openStream?: (tenantId: string) => EventSource;
  /** Solo para las pruebas: el reloj con el que se calcula la espera. */
  readonly now?: () => Date;
}

export function CasesQueuePage({
  tenantId,
  insurerLabel,
  filters,
  onFiltersChange,
  caseHref,
  openStream,
  now,
}: CasesQueuePageProps) {
  const { t } = useLocale();
  const { announce } = useAnnouncer();
  const [cola, setCola] = useState<QueueState>(EMPTY_QUEUE);
  const [problema, setProblema] = useState<ProblemView | null>(null);
  const [cargando, setCargando] = useState(true);
  const ahora = (now ?? (() => new Date()))();
  // Los filtros de la peticion, estables entre renders: sin esto el efecto que
  // consulta se volveria a disparar en cada dibujo y la cola pediria sin parar.
  const clave = JSON.stringify(filters);
  const filtrado = Object.keys(filters).length > 0;

  // La consulta vive **dentro** del efecto y quien quiere repetirla sube este
  // contador. Es lo que evita un `setState` sincrono en el cuerpo del efecto --que
  // dispara renders en cascada-- y a la vez deja que un aviso en vivo o un fallo
  // pidan de nuevo. Es la misma forma que uso la pagina de traza de U13.
  const [recarga, setRecarga] = useState(0);
  const recargar = useCallback(() => {
    setRecarga((previa) => previa + 1);
  }, []);

  useEffect(() => {
    let vigente = true;
    const pedir = async (): Promise<void> => {
      const resultado = await listCases(tenantId, JSON.parse(clave) as QueueFilters);
      if (!vigente) {
        return;
      }
      setCargando(false);
      if (!resultado.ok) {
        setProblema(resultado.problem);
        return;
      }
      setProblema(null);
      setCola(withPage(resultado.value.items, resultado.value.next_cursor ?? null));
    };
    void pedir();
    return () => {
      vigente = false;
    };
    // `recarga` esta a proposito: subirlo es la forma de volver a pedir.
  }, [tenantId, clave, recarga]);

  // El aviso en vivo (BR6.1). La reconexion con `Last-Event-ID` la hace el
  // navegador: el servidor reproduce lo posterior a ese identificador, asi que no
  // hace falta guardar nada aqui para no perder lo que paso mientras estuvo caido.
  useEffect(() => {
    const flujo = (openStream ?? openInboxStream)(tenantId);
    flujo.onmessage = (evento: MessageEvent<string>) => {
      const aviso = parseEvent(evento.data);
      if (aviso !== null) {
        setCola((previa) => reduceQueue(previa, aviso));
      }
    };
    // Una pestana, un flujo: al salir se cierra. Sin esto, volver a entrar deja dos
    // abiertos y cada aviso se aplica dos veces.
    return () => {
      flujo.close();
    };
  }, [tenantId, openStream]);

  // El resultado de filtrar se anuncia, para quien no ve la lista cambiar (BR7.5).
  const cuantos = cola.items.length;
  const anunciado = useRef<number | null>(null);
  useEffect(() => {
    if (!cargando && anunciado.current !== cuantos) {
      anunciado.current = cuantos;
      announce(t("inbox.queue.results", { count: cuantos }));
    }
  }, [cargando, cuantos, announce, t]);

  const cambiar = (campo: keyof QueueFilters, valor: string) => {
    // Se compone lo que queda en vez de borrar la clave: una propiedad ausente y una
    // puesta en `undefined` no son lo mismo en este proyecto, y es esa distincion la
    // que hace que un filtro sin valor no viaje en la direccion.
    const otros = Object.entries(filters).filter(([clave]) => clave !== campo);
    const siguiente: QueueFilters = Object.fromEntries(
      valor === "" ? otros : [...otros, [campo, valor]],
    );
    onFiltersChange(siguiente);
  };

  const traerMas = async (): Promise<void> => {
    if (cola.nextCursor === null) {
      return;
    }
    const resultado = await listCases(tenantId, filters, cola.nextCursor);
    if (!resultado.ok) {
      setProblema(resultado.problem);
      return;
    }
    setCola((previa) =>
      withMore(previa, withPage(resultado.value.items, resultado.value.next_cursor ?? null)),
    );
  };

  return (
    <div
      className="mx-auto flex w-full max-w-content flex-col gap-4 px-4 py-6"
      data-testid="inbox-queue"
    >
      <h1 className={DETAIL_TITLE}>{t("inbox.queue.title", { insurer: insurerLabel })}</h1>
      <p className="text-small text-fg-secondary" data-testid="staff-note">
        {t("inbox.staff_note")}
      </p>

      <form
        aria-label={t("inbox.queue.filters_label")}
        className="flex flex-wrap items-end gap-3"
        data-testid="queue-filters"
      >
        <FiltroSelect
          id="queue-filter-state"
          label={t("inbox.queue.filter_state")}
          value={filters.state ?? ""}
          onChange={(valor) => {
            cambiar("state", valor);
          }}
          options={ESTADOS.map((estado) => ({ value: estado, label: stateLabel(estado)(t) }))}
        />
        <FiltroSelect
          id="queue-filter-channel"
          label={t("inbox.queue.filter_channel")}
          value={filters.channel ?? ""}
          onChange={(valor) => {
            cambiar("channel", valor);
          }}
          options={CANALES.map((canal) => ({ value: canal, label: channelLabel(canal)(t) }))}
        />
        <FiltroSelect
          id="queue-filter-language"
          label={t("inbox.queue.filter_language")}
          value={filters.language ?? ""}
          onChange={(valor) => {
            cambiar("language", valor);
          }}
          options={IDIOMAS.map((idioma) => ({
            value: idioma,
            label: idioma === "es" ? t("shell.language.es") : t("shell.language.en"),
          }))}
        />
        <FiltroSelect
          id="queue-filter-priority"
          label={t("inbox.queue.filter_priority")}
          value={filters.priority ?? ""}
          onChange={(valor) => {
            cambiar("priority", valor);
          }}
          options={PRIORIDADES.map((p) => ({ value: p, label: priorityLabel(p)(t) }))}
        />
        {filtrado ? (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              onFiltersChange({});
            }}
          >
            {t("inbox.queue.filter_clear")}
          </Button>
        ) : null}
      </form>

      {problema === null ? null : (
        <InlineAlert tone="danger" role="alert" data-testid="queue-problem">
          {problema.message(t)}
        </InlineAlert>
      )}

      {cargando ? (
        <RowsSkeleton />
      ) : cola.items.length === 0 ? (
        /*
          BR1.3: se dice que ningun caso coincide y se ofrece quitar los filtros. Sin
          filtros, la frase es otra: una bandeja vacia de verdad no es un filtro que
          no acerto.
        */
        <InlineAlert
          tone="info"
          data-testid="queue-empty"
          action={
            filtrado ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  onFiltersChange({});
                }}
              >
                {t("inbox.queue.filter_clear")}
              </Button>
            ) : undefined
          }
        >
          {filtrado ? t("inbox.queue.empty_filtered") : t("inbox.queue.empty")}
        </InlineAlert>
      ) : (
        /*
          La tabla se desplaza dentro de su contenedor y no arrastra la pagina
          (accessibility-checklist, D25).
        */
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <caption className="sr-only">{t("inbox.queue.table_label")}</caption>
            <thead>
              <tr className="border-b border-hairline text-caption text-fg-secondary">
                <th scope="col" className="py-2 pr-4">
                  {t("inbox.queue.column_case")}
                </th>
                <th scope="col" className="py-2 pr-4">
                  {t("inbox.queue.column_completeness")}
                </th>
                <th scope="col" className="py-2 pr-4">
                  {t("inbox.queue.column_category")}
                </th>
                <th scope="col" className="py-2 pr-4">
                  {t("inbox.queue.column_channel")}
                </th>
                <th scope="col" className="py-2 pr-4">
                  {t("inbox.queue.column_language")}
                </th>
                <th scope="col" className="py-2 pr-4">
                  {t("inbox.queue.column_priority")}
                </th>
                <th scope="col" className="py-2">
                  {t("inbox.queue.column_waiting")}
                </th>
              </tr>
            </thead>
            <tbody>
              {cola.items.map((fila) => (
                <tr key={fila.case_id} className="border-b border-hairline align-middle">
                  <td className="py-2 pr-4">
                    {/* 44 x 44 (BR7.3): con el numero corto (`AP-1`, 2026-10-30) el
                        enlace ya no se partia en dos lineas y quedaba bajo el minimo. */}
                    <a
                      href={caseHref(fila.case_id)}
                      className="inline-flex min-h-11 min-w-11 items-center underline"
                    >
                      {t("inbox.queue.open", { case_number: fila.case_number })}
                    </a>
                  </td>
                  <td className="py-2 pr-4 font-mono text-caption">
                    {t("inbox.completeness", {
                      complete: fila.completeness_complete,
                      total: fila.completeness_total,
                    })}
                  </td>
                  <td className="py-2 pr-4">
                    <span className="flex flex-wrap items-center gap-1">
                      <Tag>{recordTypeLabel(fila.record_type)(t)}</Tag>
                      <Tag>{stateLabel(fila.state)(t)}</Tag>
                    </span>
                  </td>
                  <td className="py-2 pr-4">{channelLabel(fila.channel)(t)}</td>
                  <td className="py-2 pr-4">
                    {fila.language === "es" ? t("shell.language.es") : t("shell.language.en")}
                  </td>
                  <td className="py-2 pr-4">
                    <Tag tone={fila.priority === "high" ? "warning" : "neutral"}>
                      {priorityLabel(fila.priority)(t)}
                    </Tag>
                  </td>
                  <td className="py-2">{waitedLabel(fila.updated_at, ahora)(t)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/*
        BR6.1: cuando un aviso habla de un caso que esta pagina no tiene con su fila
        nueva, se dice que la cola quedo atras en vez de dibujar media fila con lo que
        el aviso trae. Media fila es peor que ninguna.
      */}
      {cola.staleCaseIds.length === 0 ? null : (
        <InlineAlert
          tone="info"
          data-testid="queue-stale"
          action={
            <Button type="button" variant="secondary" onClick={recargar}>
              {t("action.retry")}
            </Button>
          }
        >
          {t("inbox.queue.results", { count: cola.staleCaseIds.length })}
        </InlineAlert>
      )}

      {cola.nextCursor === null ? null : (
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            void traerMas();
          }}
        >
          {t("inbox.queue.more")}
        </Button>
      )}
    </div>
  );
}

/** Un selector de filtro, con su opcion "sin filtrar" delante. */
function FiltroSelect({
  id,
  label,
  value,
  onChange,
  options,
}: {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly options: readonly { readonly value: string; readonly label: string }[];
}) {
  const { t } = useLocale();
  return (
    <span className="flex flex-col gap-1">
      <label htmlFor={id} className="text-caption text-fg-secondary">
        {label}
      </label>
      <Select
        id={id}
        value={value}
        onChange={(evento) => {
          onChange(evento.target.value);
        }}
      >
        <option value="">{t("inbox.queue.filter_any")}</option>
        {options.map((opcion) => (
          <option key={opcion.value} value={opcion.value}>
            {opcion.label}
          </option>
        ))}
      </Select>
    </span>
  );
}
