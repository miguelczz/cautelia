// Un grupo de dos o mas botones de alternancia: la base del selector de idioma y
// del de modo (interaction-spec.md, LanguageSelector y ThemeToggle).
//
// - Rol de grupo con nombre, y cada opcion un boton con `aria-pressed`.
// - Tab entra al grupo por la opcion elegida; las flechas mueven el foco entre
//   opciones; Enter o Espacio eligen. El foco se queda en el boton pulsado.
// - Cada opcion mide al menos 44 x 44 (BR7.3) y su nombre accesible es siempre
//   el texto completo (BR7.7); lo que se ve puede ser una forma corta (`short`,
//   como los codigos EN/ES de la landing) o un icono, y entonces el texto
//   completo va en `aria-label`.
//
// Sin caja, como los enlaces de la barra (2026-10-09): monoespaciada pequena y esquinas
// suaves (`--radius-button`). La opcion elegida lleva el tinte de "elegido" --un fondo
// tenue de la marca, visible en los dos modos--, porque sobre el panel solo se
// confundia con el fondo.

import { useRef, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";

import { cn } from "./cn";

export interface SegmentedOption<T extends string> {
  readonly value: T;
  readonly label: string;
  /** El idioma del texto de la opcion, si difiere del de la pagina (BR2.4). */
  readonly lang?: string;
  readonly icon?: ReactNode;
  /** Lo que se ve en vez de `label`, que pasa a ser el nombre accesible. */
  readonly short?: ReactNode;
  /** Solo se ve el icono; `label` es su nombre accesible (`aria-label`). */
  readonly iconOnly?: boolean;
  /** El acento de una aseguradora para esta opcion (con `look="underline-tenant"`). */
  readonly style?: CSSProperties | undefined;
  /** Marca la opcion como ambito de aseguradora, para que su acento valga dentro de ella. */
  readonly tenantScope?: boolean;
}

/**
 * Como se marca la opcion elegida (2026-10-09):
 * - `tint`: fondo tenue de la marca.
 * - `underline-copper`: la linea de cobre de los enlaces de la barra bajo el texto.
 * - `underline-tenant`: la misma linea, en el acento de la aseguradora de la opcion.
 * - `accent-icon`: sin fondo; el icono elegido en el color de la marca.
 */
export type SegmentedLook = "tint" | "underline-copper" | "underline-tenant" | "accent-icon";

interface SegmentedToggleProps<T extends string> {
  readonly label: string;
  readonly value: T;
  readonly options: readonly SegmentedOption<T>[];
  readonly onChange: (value: T) => void;
  readonly testId?: string;
  /** Clases del grupo, para asentarlo en su contenedor (por ejemplo `tablet:self-start`). */
  readonly className?: string;
  readonly look?: SegmentedLook;
}

const TECLAS_SIGUIENTE = new Set(["ArrowRight", "ArrowDown"]);
const TECLAS_ANTERIOR = new Set(["ArrowLeft", "ArrowUp"]);

export function SegmentedToggle<T extends string>({
  label,
  value,
  options,
  onChange,
  testId,
  className,
  look = "tint",
}: SegmentedToggleProps<T>) {
  const botones = useRef(new Map<number, HTMLButtonElement>());

  const alTeclear = (evento: KeyboardEvent<HTMLButtonElement>, indice: number) => {
    const paso = TECLAS_SIGUIENTE.has(evento.key) ? 1 : TECLAS_ANTERIOR.has(evento.key) ? -1 : 0;
    if (paso === 0) {
      return;
    }
    evento.preventDefault();
    const destino = (indice + paso + options.length) % options.length;
    botones.current.get(destino)?.focus();
  };

  return (
    <div
      role="group"
      aria-label={label}
      data-testid={testId}
      className={cn(
        "inline-flex shrink-0 items-center gap-0.5",
        // Los nombres de las aseguradoras no caben en una fila de telefono: tres columnas
        // iguales, con el nombre en dos renglones, en vez de dejar el ultimo solo abajo.
        look === "underline-tenant" &&
          "max-tablet:grid max-tablet:w-full max-tablet:auto-cols-fr max-tablet:grid-flow-col max-tablet:items-stretch",
        className,
      )}
    >
      {options.map((opcion, indice) => {
        const elegida = opcion.value === value;
        return (
          <button
            key={opcion.value}
            ref={(nodo) => {
              if (nodo === null) {
                botones.current.delete(indice);
              } else {
                botones.current.set(indice, nodo);
              }
            }}
            type="button"
            lang={opcion.lang}
            aria-label={
              opcion.short === undefined && opcion.iconOnly !== true ? undefined : opcion.label
            }
            aria-pressed={elegida}
            tabIndex={elegida ? 0 : -1}
            onClick={() => {
              if (!elegida) {
                onChange(opcion.value);
              }
            }}
            onKeyDown={(evento) => {
              alTeclear(evento, indice);
            }}
            style={opcion.style}
            {...(opcion.tenantScope === true ? { "data-tenant-scope": "" } : {})}
            className={cn(
              "group inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-button px-3",
              "tracking-wide whitespace-nowrap",
              "transition-colors duration-[160ms] ease-out",
              look === "tint" &&
                (elegida
                  ? "bg-selected font-mono text-caption font-medium text-fg"
                  : "font-mono text-caption text-fg-secondary hover:bg-surface-alt hover:text-fg"),
              look === "underline-copper" &&
                cn("px-2 font-mono text-caption text-fg", elegida && "font-medium"),
              look === "underline-tenant" &&
                cn(
                  "px-2 font-display text-body font-semibold tracking-tight",
                  "max-tablet:min-w-0 max-tablet:px-1 max-tablet:py-1.5 max-tablet:text-center max-tablet:leading-tight max-tablet:whitespace-normal",
                  elegida ? "text-fg" : "text-fg-secondary hover:text-fg",
                ),
              look === "accent-icon" &&
                cn("font-mono text-caption", elegida ? "text-brand" : "text-fg"),
            )}
          >
            {opcion.icon}
            {opcion.iconOnly === true ? null : look === "underline-copper" ||
              look === "underline-tenant" ? (
              <span className="relative inline-block">
                {opcion.short ?? opcion.label}
                <span
                  aria-hidden="true"
                  className={cn(
                    "pointer-events-none absolute inset-x-0 -bottom-0.5 h-0.5 origin-left",
                    look === "underline-copper" ? "bg-copper" : "bg-tenant",
                    "motion-safe:transition-transform motion-safe:duration-[240ms] motion-safe:ease-out",
                    elegida
                      ? "scale-x-100"
                      : "scale-x-0 group-hover:scale-x-100 group-focus-visible:scale-x-100",
                  )}
                />
              </span>
            ) : (
              (opcion.short ?? opcion.label)
            )}
          </button>
        );
      })}
    </div>
  );
}
