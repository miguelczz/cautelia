// Los esqueletos de carga de toda pantalla (plan-estilos-2026-10.md, seccion 4).
//
// La regla: toda pantalla tiene, desde el primer cuadro, algo que dice "esto se esta
// haciendo" **con la forma de lo que viene**. Un esqueleto no es decoracion: es la
// promesa de la estructura. Si coincide con la pagina real --mismos contenedores,
// mismas alturas, misma rejilla--, el paso de esqueleto a contenido no mueve nada y la
// persona no percibe una espera, sino un llenado. Y no cuenta el porque: nadie que
// llega a una demostracion necesita saber que el proceso estaba dormido, solo que
// nada se quedo sin cargar (decision de Miguel, 2026-10-06).
//
// Cada esqueleto es una region de estado, ocupada para el lector, con un texto que
// **solo** el lector ve ("Cargando"). Lo que se ve son bloques; con movimiento
// reducido no laten.
//
// Que familia corresponde a cada direccion lo decide `app/skeleton-kinds.ts`; los
// esqueletos no saben de rutas.

import type { ReactNode } from "react";

import { useLocale } from "../i18n/locale-provider";
import { cn } from "./cn";
import {
  CHAT_COLUMN,
  CHAT_TRANSCRIPT_GUTTER,
  GUIDE_CONTENT,
  HOME_HEADER_SPACE,
  INSURER_ROW_GRID,
  LONG_PAGE_CONTENT,
  PAGE_CONTENT,
  PAGE_TITLE,
  POLICIES_CONTENT,
  POLICIES_LIST,
  POLICIES_PANES,
} from "./page-layout";
import { Skeleton } from "./skeleton";

/** Las familias de pantalla que tienen su propio esqueleto. */
export type SkeletonKind =
  | "home"
  | "guide"
  | "policies"
  | "panel"
  | "cases"
  | "compare"
  | "chat"
  | "call"
  | "inbox"
  | "case"
  | "generic";

interface RegionProps {
  readonly kind: SkeletonKind;
  /** Lo que lee el lector de pantalla; por omision, "Cargando". */
  readonly label?: string | undefined;
  readonly className?: string | undefined;
  readonly children: ReactNode;
}

function Region({ kind, label, className, children }: RegionProps) {
  const { t } = useLocale();
  return (
    <div
      role="status"
      aria-busy="true"
      data-testid="page-skeleton"
      data-skeleton-kind={kind}
      className={className}
    >
      <span className="sr-only">{label ?? t("shell.loading")}</span>
      {children}
    </div>
  );
}

/** Una linea de texto: su alto sigue al del texto que va a ocupar. */
function Line({ className }: { readonly className: string }) {
  return <Skeleton className={className} />;
}

function Pill({ className }: { readonly className: string }) {
  return <Skeleton className={cn("rounded-button", className)} />;
}

/**
 * Un renglon de texto: el alto es el del renglon que va a ocupar (tamano por
 * interlineado) y la barra es mas baja y va al centro. Asi la pantalla real no mueve
 * nada al llegar, aunque la barra se vea mas fina que las letras.
 */
function TextRow({
  height,
  bar,
}: {
  /** El alto del renglon real, p. ej. `h-5` para texto pequeno. */
  readonly height: string;
  /** La barra: alto y ancho. */
  readonly bar: string;
}) {
  return (
    <div className={cn("flex items-center", height)}>
      <Skeleton className={bar} />
    </div>
  );
}

// --- El inicio ----------------------------------------------------------------

function HomeSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region kind="home" label={label} className={PAGE_CONTENT}>
      <div className={cn("flex max-w-[46rem] flex-col gap-3", HOME_HEADER_SPACE)}>
        {/* Dos renglones de titulo, a 1,05 veces el tamano que tendra en esta ventana. */}
        <div className={PAGE_TITLE}>
          <div className="flex h-[1.05em] items-center">
            <Skeleton className="h-[0.7em] w-4/5" />
          </div>
          <div className="flex h-[1.05em] items-center">
            <Skeleton className="h-[0.7em] w-3/5" />
          </div>
        </div>
        <TextRow height="h-[1.55rem]" bar="h-4 w-1/2" />
      </div>
      <div className="flex flex-col gap-3">
        <TextRow height="h-[1.8rem]" bar="h-5 w-3/5" />
        <div className="flex flex-col border-b border-hairline">
          {/* Cuantos renglones de descripcion lleva cada fila: lo tipico, dos, una y dos. */}
          {[2, 1, 2].map((renglones, fila) => (
            <div key={fila} className={INSURER_ROW_GRID}>
              <div className="flex items-start gap-4">
                <Skeleton className="size-12 shrink-0" />
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <TextRow height="h-7" bar="h-5 w-1/3" />
                  {Array.from({ length: renglones }, (_, renglon) => (
                    <TextRow
                      key={renglon}
                      height="h-5"
                      bar={renglon === 0 ? "h-3 w-5/6" : "h-3 w-2/3"}
                    />
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 tablet:justify-end">
                <Pill className="h-11 w-28" />
                <Pill className="h-11 w-24" />
                <Pill className="h-11 w-32" />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="flex justify-end">
        <Pill className="h-11 w-36" />
      </div>
    </Region>
  );
}

// --- La guia ------------------------------------------------------------------

/** La guia con su forma: contexto arriba, los pasos en una fila y dos bloques abajo. */
function GuideSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region kind="guide" label={label} className={GUIDE_CONTENT}>
      <div className="grid gap-x-6 gap-y-4 desktop:grid-cols-2 desktop:items-end">
        <div className="flex flex-col gap-3 roomy:gap-[clamp(0.25rem,1.2dvh,0.75rem)]">
          <div className={PAGE_TITLE}>
            <div className="flex h-[1.05em] items-center">
              <Skeleton className="h-[0.7em] w-1/2" />
            </div>
          </div>
          {/* Los renglones del parrafo de contexto: su alto es el del texto que van a ocupar. */}
          <div className="flex flex-col text-lead roomy:text-[length:clamp(0.9375rem,2dvh,1.2rem)]">
            <TextRow height="h-[1.4em]" bar="h-3.5 w-full" />
            <TextRow height="h-[1.4em]" bar="h-3.5 w-11/12" />
            <TextRow height="h-[1.4em]" bar="h-3.5 w-2/3" />
          </div>
        </div>
        <div className="flex flex-col gap-2 border-l-2 border-hairline pl-4">
          <TextRow height="h-[1.55rem]" bar="h-4 w-11/12" />
          <TextRow height="h-[1.55rem]" bar="h-4 w-1/2" />
        </div>
      </div>
      <div className="flex flex-col gap-3 roomy:gap-2">
        <div className="flex items-center justify-between gap-6">
          <TextRow height="h-[1.8rem]" bar="h-5 w-32" />
          <Pill className="h-11 w-48" />
        </div>
        <div className="grid gap-x-6 gap-y-4 tablet:grid-cols-2 desktop:grid-cols-4">
          {[2, 3, 2, 2].map((renglones, paso) => (
            <div key={paso} className="flex flex-col gap-1 border-t-2 border-hairline pt-3">
              <div className="flex h-[1.7rem] items-center gap-2.5">
                <Skeleton className="h-3 w-5" />
                <Skeleton className="h-4 w-3/5" />
              </div>
              <div className="flex flex-col">
                {Array.from({ length: renglones }, (_, renglon) => (
                  <TextRow
                    key={renglon}
                    height="h-5"
                    bar={renglon === renglones - 1 ? "h-3 w-1/2" : "h-3 w-full"}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="grid gap-x-6 gap-y-8 desktop:grid-cols-2">
        <div className="flex flex-col gap-3 roomy:gap-2">
          <TextRow height="h-[1.8rem]" bar="h-5 w-2/5" />
          <div className="flex flex-col gap-1">
            {[0, 1, 2, 3, 4].map((fila) => (
              <Skeleton key={fila} className="h-9 w-full" />
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-3 roomy:gap-2">
          <TextRow height="h-[1.8rem]" bar="h-5 w-2/5" />
          <div className="flex flex-col">
            <TextRow height="h-5" bar="h-3 w-full" />
            <TextRow height="h-5" bar="h-3 w-3/5" />
          </div>
          <div className="flex flex-col gap-2">
            {[0, 1, 2].map((fila) => (
              <Skeleton key={fila} className="h-[4.5rem] w-full" />
            ))}
          </div>
        </div>
      </div>
    </Region>
  );
}

// --- Las polizas ---------------------------------------------------------------

/**
 * La lista y el detalle de las polizas, con las clases de la pantalla real: la lista de
 * seis tarjetas crece y se reparte igual que la de verdad, y el detalle ocupa el mismo
 * marco. Tambien sirve de cuerpo mientras llegan las polizas de una aseguradora, dentro
 * de una pantalla que ya tiene su titulo y su selector.
 */
function PoliciesPanes() {
  return (
    <>
      <div className={POLICIES_LIST}>
        {[0, 1, 2, 3, 4, 5].map((poliza) => (
          <div key={poliza} className="roomy:flex">
            <Skeleton className="h-[5.1rem] w-full rounded-surface roomy:h-auto roomy:min-h-[4.75rem] roomy:flex-1" />
          </div>
        ))}
      </div>
      <div className="min-w-0 roomy:relative">
        <Skeleton className="h-[28rem] w-full rounded-surface roomy:absolute roomy:inset-0 roomy:h-auto" />
      </div>
    </>
  );
}

export function PoliciesBodySkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region kind="policies" label={label} className={POLICIES_PANES}>
      <PoliciesPanes />
    </Region>
  );
}

function PoliciesSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region kind="policies" label={label} className={POLICIES_CONTENT}>
      <div className="flex flex-col gap-6 roomy:flex-row roomy:items-end roomy:justify-between roomy:gap-8">
        <div className="flex max-w-[46rem] flex-col gap-2">
          <div className={PAGE_TITLE}>
            <div className="flex h-[1.05em] items-center">
              <Skeleton className="h-[0.7em] w-72 max-w-full" />
            </div>
          </div>
          <TextRow height="h-[1.55rem]" bar="h-4 w-96 max-w-full" />
        </div>
        <div className="flex gap-2">
          {[0, 1, 2].map((aseguradora) => (
            <Pill key={aseguradora} className="h-11 w-28" />
          ))}
        </div>
      </div>
      <div className={POLICIES_PANES}>
        <PoliciesPanes />
      </div>
    </Region>
  );
}

// --- Las pantallas de datos (cifras y gasto) -----------------------------------

/** El cuerpo de un panel mientras llegan sus cifras; el titulo y la bajada son fijos y se ven. */
export function PanelBodySkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region kind="panel" label={label} className="flex flex-col gap-8">
      {[0, 1, 2].map((bloque) => (
        <div key={bloque} className="flex flex-col gap-3">
          <Line className="h-6 w-1/4" />
          <Line className="h-16 w-full" />
        </div>
      ))}
    </Region>
  );
}

function PanelSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region kind="panel" label={label} className={LONG_PAGE_CONTENT}>
      <div className="flex max-w-[46rem] flex-col gap-4">
        <div className={cn(PAGE_TITLE, "flex flex-col")}>
          <Line className="h-[1.05em] w-1/2" />
        </div>
        <Line className="h-6 w-4/5" />
      </div>
      <div className="flex flex-col gap-8">
        {[0, 1, 2].map((bloque) => (
          <div key={bloque} className="flex flex-col gap-3">
            <Line className="h-6 w-1/4" />
            <Line className="h-16 w-full" />
          </div>
        ))}
      </div>
    </Region>
  );
}

/** La pagina de casos: que es un caso, el tuyo y los de ejemplo por estado. */
function CasesSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region kind="cases" label={label} className={LONG_PAGE_CONTENT}>
      <div className="flex max-w-[46rem] flex-col gap-3">
        <div className={cn(PAGE_TITLE, "flex flex-col")}>
          <Line className="h-[1.05em] w-1/3" />
        </div>
        <TextRow height="h-[1.55rem]" bar="h-4 w-full" />
        <TextRow height="h-[1.55rem]" bar="h-4 w-3/5" />
      </div>
      {/* Tus casos: el titulo, su bajada y una fila. */}
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <TextRow height="h-[1.8rem]" bar="h-5 w-1/4" />
          <TextRow height="h-5" bar="h-3 w-1/3" />
        </div>
        <Skeleton className="h-24 w-full rounded-surface" />
      </div>
      {/* Casos de ejemplo: el titulo, el selector de aseguradora y un grupo con sus filas. */}
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <TextRow height="h-[1.8rem]" bar="h-5 w-1/3" />
          <TextRow height="h-5" bar="h-3 w-3/5" />
        </div>
        <div className="flex gap-2">
          {[0, 1, 2].map((aseguradora) => (
            <Pill key={aseguradora} className="h-11 w-28" />
          ))}
        </div>
        <div className="flex flex-col gap-3">
          <TextRow height="h-[1.8rem]" bar="h-5 w-1/4" />
          <Skeleton className="h-44 w-full rounded-surface" />
        </div>
      </div>
    </Region>
  );
}

/**
 * La comparacion con su forma: el titulo y su bajada de dos renglones, la tarjeta de la
 * pregunta --etiqueta y aviso, el cuadro de texto, las preguntas de ejemplo en tres
 * renglones y el boton-- y las tres columnas con su franja, su encabezado y el esbozo de
 * la respuesta. Las alturas son las de la pantalla real, asi el contenido no salta al llegar.
 */
function CompareSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region kind="compare" label={label} className={LONG_PAGE_CONTENT}>
      <div className="flex max-w-[46rem] flex-col gap-3">
        <div className={PAGE_TITLE}>
          <div className="flex h-[1.05em] items-center">
            <Skeleton className="h-[0.7em] w-3/5" />
          </div>
        </div>
        <div className="flex flex-col">
          <TextRow height="h-[1.7rem]" bar="h-4 w-full" />
          <TextRow height="h-[1.7rem]" bar="h-4 w-2/3" />
        </div>
      </div>
      <div className="flex flex-col gap-4 rounded-surface border border-hairline bg-surface p-4 tablet:p-6">
        <div className="flex flex-col gap-1">
          <TextRow height="h-[1.55rem]" bar="h-4 w-48" />
          <TextRow height="h-[1.05rem]" bar="h-2.5 w-3/4 tablet:w-1/2" />
        </div>
        <Skeleton className="h-[5.75rem] w-full" />
        <div className="flex flex-col gap-2">
          <TextRow height="h-[1.05rem]" bar="h-2.5 w-32" />
          <div className="flex flex-wrap gap-2">
            {["w-72", "w-64", "w-80", "w-72", "w-80", "w-64", "w-56", "w-72"].map(
              (ancho, ejemplo) => (
                <Pill key={ejemplo} className={cn("h-11 max-w-full", ancho)} />
              ),
            )}
          </div>
        </div>
        <Pill className="h-11 w-52" />
      </div>
      <div className="grid gap-4 desktop:grid-cols-3">
        {[0, 1, 2].map((columna) => (
          <div
            key={columna}
            className="flex flex-col overflow-hidden rounded-surface border border-hairline bg-surface"
          >
            <div className="h-1 bg-surface-alt" />
            <div className="flex flex-col gap-3 p-4 tablet:p-5">
              <div className="flex items-start gap-3">
                <Skeleton className="size-10 shrink-0" />
                <div className="flex min-w-0 flex-1 flex-col">
                  <TextRow height="h-7" bar="h-4 w-1/2" />
                  <TextRow height="h-5" bar="h-3 w-2/3" />
                </div>
              </div>
              <TextRow height="h-[1.05rem]" bar="h-2.5 w-3/4" />
            </div>
            <div className="flex flex-1 flex-col gap-3 border-t border-hairline p-4 tablet:p-5">
              <div className="flex flex-col">
                <TextRow height="h-[1.55rem]" bar="h-4 w-full" />
                <TextRow height="h-[1.55rem]" bar="h-4 w-2/3" />
              </div>
              <div className="flex flex-col gap-2.5 pt-1">
                <Skeleton className="h-2.5 w-full rounded-pill" />
                <Skeleton className="h-2.5 w-11/12 rounded-pill" />
                <Skeleton className="h-2.5 w-2/3 rounded-pill" />
              </div>
              <Skeleton className="h-[3.25rem] w-full" />
            </div>
          </div>
        ))}
      </div>
    </Region>
  );
}

// --- Las conversaciones --------------------------------------------------------

function ChatSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    // La forma de la pantalla real (2026-10-08): sin caja, una columna de lectura con
    // el encabezado arriba, la agente en renglones sin burbuja, la persona en una
    // burbuja a la derecha y el cuadro de escribir abajo.
    <Region kind="chat" label={label} className="flex min-h-0 w-full flex-1 flex-col">
      <div className={cn(CHAT_COLUMN, "flex items-center gap-3 pt-4 pb-2 tablet:pt-6")}>
        <div className="flex flex-1 flex-col gap-1">
          <TextRow height="h-6" bar="h-4 w-1/2 tablet:w-1/3" />
          <TextRow height="h-4" bar="h-3 w-1/3 tablet:w-1/4" />
        </div>
        {/* Las acciones del encabezado en su grupo: documentos y pensamiento con nombre, reiniciar de solo icono. */}
        <div className="flex items-center gap-1 tablet:gap-0.5 tablet:rounded-control tablet:border tablet:border-hairline tablet:p-0.5">
          <Pill className="h-11 w-11 tablet:w-32" />
          <Pill className="h-11 w-11 tablet:w-44" />
          <Pill className="h-11 w-11" />
        </div>
      </div>
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col gap-6 py-6 tablet:gap-7 tablet:py-8",
          CHAT_TRANSCRIPT_GUTTER,
        )}
      >
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center gap-2">
            <Pill className="size-6 shrink-0" />
            <Line className="h-3 w-20" />
          </div>
          <div className="flex max-w-[72ch] flex-col gap-1">
            <TextRow height="h-[1.55rem]" bar="h-3.5 w-full" />
            <TextRow height="h-[1.55rem]" bar="h-3.5 w-11/12" />
            <TextRow height="h-[1.55rem]" bar="h-3.5 w-2/5" />
          </div>
        </div>
        <Skeleton className="h-11 w-1/2 self-end rounded-bubble tablet:w-2/5" />
      </div>
      <div className={cn(CHAT_COLUMN, "flex flex-col gap-2 pt-1 pb-3 tablet:pb-4")}>
        <Skeleton className="h-14 w-full rounded-bubble" />
        <div className="flex h-4 justify-center">
          <Line className="h-3 w-2/3 tablet:w-1/2" />
        </div>
      </div>
    </Region>
  );
}

function CallSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region
      kind="call"
      label={label}
      className="mx-auto flex w-full max-w-2xl flex-col gap-4 px-4 py-6"
    >
      <Line className="h-8 w-1/2" />
      <Line className="h-5 w-3/4" />
      <Skeleton className="h-40 w-full rounded-surface" />
      <Pill className="h-11 w-40" />
    </Region>
  );
}

// --- La bandeja y el caso ------------------------------------------------------

/** Las filas de una lista que todavia no llego; dentro de una pantalla que ya tiene sus filtros. */
export function RowsSkeleton({
  rows = 6,
  label,
}: {
  readonly rows?: number;
  readonly label?: string | undefined;
}) {
  return (
    <Region kind="inbox" label={label} className="flex flex-col gap-3">
      {Array.from({ length: rows }, (_, fila) => (
        <Line key={fila} className="h-14 w-full" />
      ))}
    </Region>
  );
}

function InboxSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region
      kind="inbox"
      label={label}
      className="mx-auto flex w-full max-w-content flex-col gap-4 px-4 py-6"
    >
      <Line className="h-8 w-1/3" />
      <div className="flex flex-wrap gap-2">
        {[0, 1, 2, 3].map((filtro) => (
          <Pill key={filtro} className="h-11 w-32" />
        ))}
      </div>
      <div className="flex flex-col gap-3">
        {[0, 1, 2, 3, 4, 5].map((fila) => (
          <Line key={fila} className="h-14 w-full" />
        ))}
      </div>
    </Region>
  );
}

function CaseSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region
      kind="case"
      label={label}
      className="mx-auto flex w-full max-w-content flex-col gap-4 px-4 py-6"
    >
      <Line className="h-8 w-1/3" />
      <Line className="h-5 w-1/2" />
      <div className="grid gap-4 tablet:grid-cols-2">
        {[0, 1, 2, 3, 4, 5].map((bloque) => (
          <Skeleton key={bloque} className="h-28 w-full rounded-surface" />
        ))}
      </div>
    </Region>
  );
}

// --- Cualquier otra ------------------------------------------------------------

function GenericSkeleton({ label }: { readonly label?: string | undefined }) {
  return (
    <Region
      kind="generic"
      label={label}
      className="mx-auto flex w-full max-w-content flex-col gap-4 px-4 py-16 tablet:px-8"
    >
      <Line className="h-10 w-2/3" />
      <Line className="h-5 w-1/2" />
      <Line className="mt-8 h-24 w-full" />
      <Line className="h-24 w-full" />
    </Region>
  );
}

/** El esqueleto de una familia de pantalla, con la forma que va a tener. */
export function PageSkeleton({
  kind,
  label,
}: {
  readonly kind: SkeletonKind;
  readonly label?: string | undefined;
}) {
  switch (kind) {
    case "home":
      return <HomeSkeleton label={label} />;
    case "guide":
      return <GuideSkeleton label={label} />;
    case "policies":
      return <PoliciesSkeleton label={label} />;
    case "panel":
      return <PanelSkeleton label={label} />;
    case "cases":
      return <CasesSkeleton label={label} />;
    case "compare":
      return <CompareSkeleton label={label} />;
    case "chat":
      return <ChatSkeleton label={label} />;
    case "call":
      return <CallSkeleton label={label} />;
    case "inbox":
      return <InboxSkeleton label={label} />;
    case "case":
      return <CaseSkeleton label={label} />;
    case "generic":
      return <GenericSkeleton label={label} />;
  }
}
