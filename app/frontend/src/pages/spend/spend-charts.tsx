// Las graficas del tablero de gasto, dibujadas en SVG (2026-10-09).
//
// Sin biblioteca de graficas: son cuatro formas simples --barras apiladas por dia,
// una dona, barras horizontales y un medidor-- y una biblioteca sumaria mas peso que
// todo el tablero. Los colores son tokens del tema, asi que siguen al modo claro y
// al oscuro. Cada grafica dice con texto lo mismo que dibuja: la dona tiene su
// leyenda con cifras, y las barras por dia, una linea que nombra el dia elegido.

import { useState, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";

import type {
  ComparisonPart,
  DaySpend,
  ProviderSpend,
  SpendActivity,
  SpendTotal,
} from "../../shared/api-client/spend";
import { useLocale } from "../../shared/i18n/locale-provider";
import { cn } from "../../shared/ui/cn";
import { useAmount, useShortDay, useUsd, type AmountView } from "./spend-format";
import {
  ACTIVITIES,
  activityColor,
  activityName,
  providerName,
  providerRole,
} from "./spend-labels";

type PorActividad = Partial<Record<SpendActivity, number>>;

function delDia(dia: DaySpend): PorActividad {
  const valores: PorActividad = {};
  for (const parte of dia.activities) {
    valores[parte.activity] = Number(parte.total.measured_usd);
  }
  return valores;
}

function suma(valores: PorActividad): number {
  return Object.values(valores).reduce((total, valor) => total + valor, 0);
}

/** Las actividades que aparecen en algun dia, en el orden fijo de la leyenda. */
function presentes(dias: readonly PorActividad[]): SpendActivity[] {
  return ACTIVITIES.filter((actividad) => dias.some((dia) => (dia[actividad] ?? 0) > 0));
}

export function Swatch({ activity }: { readonly activity: SpendActivity }) {
  return (
    <svg aria-hidden="true" width="10" height="10" className="shrink-0">
      <rect width="10" height="10" rx="2" fill={activityColor(activity)} />
    </svg>
  );
}

// --- Gasto por dia ----------------------------------------------------------------

const ANCHO = 600;
const ALTO = 160;

export function DailyBars({ days }: { readonly days: readonly DaySpend[] }) {
  const { t } = useLocale();
  const usd = useUsd();
  const corto = useShortDay();
  const valores = days.map(delDia);
  const totales = valores.map(suma);
  const maximo = Math.max(...totales, 0);
  const ultimoConGasto = totales.findLastIndex((total) => total > 0);
  const [elegido, setElegido] = useState<number>(
    ultimoConGasto === -1 ? days.length - 1 : ultimoConGasto,
  );
  const series = presentes(valores);

  if (days.length === 0) {
    return null;
  }
  if (maximo === 0) {
    return <p className="text-body text-fg-secondary">{t("spend_panel.daily.quiet")}</p>;
  }

  const paso = ANCHO / days.length;
  const barra = Math.max(paso * 0.62, 2);
  const indice = Math.min(Math.max(elegido, 0), days.length - 1);
  const diaElegido = days[indice];

  function mover(evento: KeyboardEvent<HTMLDivElement>) {
    if (evento.key === "ArrowLeft") {
      evento.preventDefault();
      setElegido(Math.max(indice - 1, 0));
    } else if (evento.key === "ArrowRight") {
      evento.preventDefault();
      setElegido(Math.min(indice + 1, days.length - 1));
    }
  }

  return (
    <figure className="flex flex-col gap-3" data-testid="spend-daily">
      <div className="flex gap-3">
        <div
          aria-hidden="true"
          className="flex w-16 shrink-0 flex-col justify-between py-0.5 text-right text-caption text-fg-tertiary tabular-nums"
        >
          <span>{usd(maximo)}</span>
          <span>{usd(maximo / 2)}</span>
          <span>{usd(0)}</span>
        </div>
        {/* Un deslizador sobre los dias: las flechas eligen el dia y el lector de
            pantalla anuncia lo que costo, igual que la linea de abajo. */}
        <div
          role="slider"
          tabIndex={0}
          aria-label={t("spend_panel.daily.title")}
          aria-valuemin={0}
          aria-valuemax={days.length - 1}
          aria-valuenow={indice}
          aria-valuetext={t("spend_panel.daily.bar", {
            date: corto(days[indice]?.day ?? ""),
            amount: usd(totales[indice] ?? 0),
          })}
          onKeyDown={mover}
          className="relative min-w-0 flex-1 rounded-control focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-focus"
        >
          <svg
            viewBox={`0 0 ${String(ANCHO)} ${String(ALTO)}`}
            preserveAspectRatio="none"
            className="block h-40 w-full tablet:h-48"
            aria-hidden="true"
          >
            {[0, 0.5, 1].map((linea) => (
              <line
                key={linea}
                x1="0"
                x2={ANCHO}
                y1={ALTO * linea}
                y2={ALTO * linea}
                stroke="var(--ut-hairline)"
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {valores.map((dia, posicion) => {
              let base = ALTO;
              const x = posicion * paso + (paso - barra) / 2;
              return (
                <g key={days[posicion]?.day} opacity={posicion === indice ? 1 : 0.78}>
                  {series.map((actividad) => {
                    const alto = ((dia[actividad] ?? 0) / maximo) * (ALTO - 4);
                    if (alto <= 0) {
                      return null;
                    }
                    base -= alto;
                    return (
                      <rect
                        key={actividad}
                        x={x}
                        y={base}
                        width={barra}
                        height={Math.max(alto, 1)}
                        fill={activityColor(actividad)}
                      />
                    );
                  })}
                  <rect
                    x={posicion * paso}
                    y="0"
                    width={paso}
                    height={ALTO}
                    fill="transparent"
                    className="cursor-pointer"
                    onMouseEnter={() => {
                      setElegido(posicion);
                    }}
                    onClick={() => {
                      setElegido(posicion);
                    }}
                  />
                </g>
              );
            })}
            <rect
              x={indice * paso}
              y="0"
              width={paso}
              height={ALTO}
              fill="var(--ut-selected)"
              pointerEvents="none"
            />
          </svg>
        </div>
      </div>
      <div
        aria-hidden="true"
        className="ml-19 flex justify-between text-caption text-fg-tertiary tabular-nums"
      >
        <span>{corto(days[0]?.day ?? "")}</span>
        <span>{corto(days[Math.floor(days.length / 2)]?.day ?? "")}</span>
        <span>{corto(days[days.length - 1]?.day ?? "")}</span>
      </div>
      {diaElegido === undefined ? null : (
        <figcaption
          aria-live="polite"
          className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-control bg-surface-alt px-3 py-2 text-small text-fg"
          data-testid="spend-daily-detail"
        >
          <span className="font-medium">
            {t("spend_panel.daily.bar", {
              date: corto(diaElegido.day),
              amount: usd(totales[indice] ?? 0),
            })}
          </span>
          {series
            .filter((actividad) => (valores[indice]?.[actividad] ?? 0) > 0)
            .map((actividad) => (
              <span key={actividad} className="inline-flex items-center gap-1.5 text-fg-secondary">
                <Swatch activity={actividad} />
                {activityName(actividad)(t)} {usd(valores[indice]?.[actividad] ?? 0)}
              </span>
            ))}
        </figcaption>
      )}
    </figure>
  );
}

// --- La dona por actividad ----------------------------------------------------------

/** El radio que hace que la circunferencia mida 100: cada porcentaje es un trazo. */
const RADIO = 15.915494;

export function ActivityDonut({
  parts,
  center,
  centerLabel,
}: {
  readonly parts: readonly { readonly activity: SpendActivity; readonly value: number }[];
  readonly center: string;
  readonly centerLabel: string;
}) {
  const total = parts.reduce((acumulado, parte) => acumulado + parte.value, 0);
  let recorrido = 0;
  return (
    <div className="relative mx-auto aspect-square w-44 shrink-0 tablet:w-52">
      <svg viewBox="0 0 42 42" className="block size-full -rotate-90" aria-hidden="true">
        <circle
          cx="21"
          cy="21"
          r={RADIO}
          fill="none"
          stroke="var(--ut-surface-alt)"
          strokeWidth="5"
        />
        {total > 0
          ? parts.map((parte) => {
              const porcentaje = (parte.value / total) * 100;
              const trazo = (
                <circle
                  key={parte.activity}
                  cx="21"
                  cy="21"
                  r={RADIO}
                  fill="none"
                  stroke={activityColor(parte.activity)}
                  strokeWidth="5"
                  strokeDasharray={`${String(Math.max(porcentaje - 0.6, 0.4))} ${String(100 - Math.max(porcentaje - 0.6, 0.4))}`}
                  strokeDashoffset={-recorrido}
                />
              );
              recorrido += porcentaje;
              return trazo;
            })
          : null}
      </svg>
      {/* El hueco de la dona mide poco mas de la mitad del circulo: la cifra se adapta a
          ese hueco y no al circulo entero, igual que las tarjetas (2026-10-11). */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="@container flex w-[58%] flex-col items-center text-center">
          <span
            className="font-display text-fg tabular-nums text-[length:clamp(0.875rem,calc(100cqi/(var(--figure-chars)*0.6)),1.44rem)]"
            style={{ "--figure-chars": center.length } as CSSProperties}
            data-testid="spend-donut-center"
          >
            {center}
          </span>
          <span className="text-caption text-fg-secondary">{centerLabel}</span>
        </div>
      </div>
    </div>
  );
}

// --- Barras por proveedor ------------------------------------------------------------

/**
 * Un importe en una fila: la cifra y, debajo y mas chica, lo que la aclara.
 *
 * Con `withNote` en falso solo sale la cifra: el panel de "En que se va" la quiere sin
 * renglon extra (Miguel, 2026-10-12: "a la gente solo le importa lo que se esta
 * consumiendo").
 */
export function Amount({
  view,
  withNote = true,
}: {
  readonly view: AmountView;
  readonly withNote?: boolean;
}) {
  return (
    <span className="flex shrink-0 flex-col items-end text-right text-fg tabular-nums">
      <span>{view.main}</span>
      {!withNote || view.note === null ? null : (
        <span className="text-caption text-fg-secondary" data-testid="spend-amount-note">
          {view.note}
        </span>
      )}
    </span>
  );
}

/**
 * La aclaracion de un importe, **encima** de la fila y alineada a la derecha. Si otra fila
 * del panel la tiene, las que no la tienen guardan el mismo renglon vacio: asi las cuatro
 * filas miden lo mismo por dentro y la barra queda a la misma distancia de su nombre,
 * lleve o no una aclaracion.
 */
function NoteAbove({ note, reserve }: { readonly note: string | null; readonly reserve: boolean }) {
  if (note === null) {
    return reserve ? (
      <span aria-hidden="true" className="invisible self-end text-caption">
        {"\u00a0"}
      </span>
    ) : null;
  }
  return (
    <span
      className="self-end text-right text-caption text-fg-secondary tabular-nums"
      data-testid="spend-amount-note"
    >
      {note}
    </span>
  );
}

/** Una fila de barras: quien, cuanto, y una barra proporcional al dinero medido. */
function BarRow({
  name,
  measured,
  maximum,
  amount,
  noteAbove = false,
  reserveNote = false,
  children,
}: {
  readonly name: string;
  readonly measured: number;
  readonly maximum: number;
  readonly amount: AmountView;
  /** La aclaracion del importe va encima de la fila y no debajo de la cifra. */
  readonly noteAbove?: boolean;
  /** Dejar el renglon de la aclaracion aunque esta fila no la tenga. */
  readonly reserveNote?: boolean;
  readonly children?: ReactNode;
}) {
  return (
    <li className="flex flex-col gap-1.5">
      {noteAbove ? <NoteAbove note={amount.note} reserve={reserveNote} /> : null}
      <div className="flex items-baseline justify-between gap-4">
        <span className="min-w-0 font-medium text-fg">{name}</span>
        <Amount view={amount} withNote={!noteAbove} />
      </div>
      <div className="h-2 rounded-pill bg-surface-alt">
        <div
          className="h-2 rounded-pill bg-brand"
          style={{
            width: `${String(maximum > 0 ? Math.max((measured / maximum) * 100, measured > 0 ? 1.5 : 0) : 0)}%`,
          }}
        />
      </div>
      {children}
    </li>
  );
}

function byMeasuredDescending<T extends { readonly total: SpendTotal }>(rows: readonly T[]): T[] {
  return [...rows].sort((a, b) => Number(b.total.measured_usd) - Number(a.total.measured_usd));
}

export function ProviderBars({
  providers,
  compact = false,
  fill = false,
}: {
  readonly providers: readonly ProviderSpend[];
  readonly compact?: boolean;
  /** Ocupar el alto que sobra del panel, repartiendo los proveedores en vez de dejar un hueco abajo. */
  readonly fill?: boolean;
}) {
  const { t } = useLocale();
  const amountOf = useAmount();
  const ordenados = byMeasuredDescending(providers);
  const maximo = Math.max(...ordenados.map((p) => Number(p.total.measured_usd)), 0);
  // En el panel completo la aclaracion ("+ 761 consultas · plan gratuito") va encima de la
  // cifra, para que no empuje la barra; si alguna fila la tiene, todas guardan su renglon.
  const hayAclaraciones =
    !compact &&
    ordenados.some((proveedor) => amountOf(proveedor.total, proveedor.unpriced).note !== null);
  return (
    <ul
      className={cn(
        "flex flex-col",
        compact ? "gap-3" : hayAclaraciones ? "gap-2" : "gap-5",
        fill && "flex-1 justify-between",
      )}
    >
      {ordenados.map((proveedor) => (
        <BarRow
          key={proveedor.provider}
          name={providerName(proveedor.provider)(t)}
          measured={Number(proveedor.total.measured_usd)}
          maximum={maximo}
          amount={amountOf(proveedor.total, proveedor.unpriced)}
          noteAbove={!compact}
          reserveNote={hayAclaraciones}
        >
          {compact ? null : (
            <span className="text-small text-fg-secondary">
              {providerRole(proveedor.provider)(t)}
            </span>
          )}
          {compact || (proveedor.models ?? []).length === 0 ? null : (
            <span
              className="flex flex-wrap items-center gap-x-2 gap-y-1 text-small text-fg-secondary"
              data-testid="spend-models"
            >
              {t("spend_panel.provider.models")}
              {(proveedor.models ?? []).map((modelo) => (
                <code
                  key={modelo.model}
                  className="rounded-button bg-surface-alt px-2 py-0.5 font-mono text-caption text-fg"
                >
                  {modelo.model}
                </code>
              ))}
            </span>
          )}
        </BarRow>
      ))}
    </ul>
  );
}

/** Lo que cobro cada aseguradora dentro de una comparacion, con la misma forma. */
export function InsurerBars({
  parts,
  nameOf,
}: {
  readonly parts: readonly ComparisonPart[];
  readonly nameOf: (tenantId: string) => string;
}) {
  const amountOf = useAmount();
  const ordenadas = byMeasuredDescending(parts);
  const maximo = Math.max(...ordenadas.map((p) => Number(p.total.measured_usd)), 0);
  return (
    <ul className="flex flex-col gap-3" data-testid="spend-insurer-parts">
      {ordenadas.map((parte) => (
        <BarRow
          key={parte.tenant_id}
          name={nameOf(parte.tenant_id)}
          measured={Number(parte.total.measured_usd)}
          maximum={maximo}
          amount={amountOf(parte.total, parte.unpriced)}
        />
      ))}
    </ul>
  );
}

// --- El medidor del presupuesto ------------------------------------------------------

export function BudgetMeter({
  spent,
  cap,
  alert,
}: {
  readonly spent: number;
  readonly cap: number;
  readonly alert: number;
}) {
  const lleno = cap > 0 ? Math.min(spent / cap, 1) : 0;
  const aviso = cap > 0 ? Math.min(alert / cap, 1) : 0;
  return (
    <div aria-hidden="true" className="relative h-2.5 rounded-pill bg-surface-alt">
      <div
        className="h-2.5 rounded-pill bg-brand"
        style={{ width: `${String(Math.max(lleno * 100, spent > 0 ? 1 : 0))}%` }}
      />
      <div
        className="absolute -top-1 h-4.5 w-0.5 rounded-pill bg-warning"
        style={{ left: `${String(aviso * 100)}%` }}
      />
    </div>
  );
}
