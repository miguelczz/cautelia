// Boton: primitiva del patron de shadcn/ui sobre `Slot` de Radix, tematizada
// con los tokens (BR1.5) y nunca con su aspecto por defecto.
//
// Sus siete estados (design-system-mapping.md, principio 6): por defecto, encima
// (solo con puntero fino), foco (el anillo global de `:focus-visible`), activo
// (escala 0,97 en 120 ms, sin escala con movimiento reducido), deshabilitado,
// cargando (`loading`: ocupado para el lector y sin segundo clic) y error
// (`invalid`: anillo de peligro). El rol de boton no admite `aria-invalid`, asi
// que el error se marca con `data-invalid` y **lo dice el mensaje** que lo
// acompana, nunca solo el color (BR7.6). Mide al menos 44 x 44 (BR7.3).

import { Slot } from "@radix-ui/react-slot";
import { CircleNotchIcon } from "@phosphor-icons/react";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes, Ref } from "react";

import { cn } from "./cn";

export const buttonVariants = cva(
  [
    "inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-button px-5",
    "font-body text-body font-medium whitespace-nowrap select-none no-underline",
    "transition-[background-color,border-color,color,box-shadow,transform] duration-[160ms] ease-out",
    "motion-safe:active:scale-[0.97] motion-safe:active:duration-[120ms]",
    "disabled:cursor-not-allowed disabled:opacity-60",
    "aria-busy:cursor-progress",
    "data-invalid:ring-2 data-invalid:ring-danger",
  ],
  {
    variants: {
      variant: {
        primary: "bg-brand text-on-brand hover:bg-brand-hover motion-safe:hover:-translate-y-px",
        secondary: "border border-control bg-transparent text-fg hover:bg-surface-alt",
        ghost: "bg-transparent text-fg hover:bg-surface-alt",
        // El boton principal de una aseguradora: su acento de fondo y el texto que
        // pide el contraste de cada modo (BR1.6).
        tenant: "bg-tenant text-on-tenant hover:ring-2 hover:ring-inset hover:ring-on-tenant/40",
        // La accion secundaria de una aseguradora: solo su acento, en el borde y en la
        // letra, para que acompane al boton principal sin quitarle protagonismo.
        "tenant-outline": "border border-tenant bg-transparent text-tenant hover:bg-tenant/10",
      },
      size: {
        default: "",
        compact: "px-4 text-small",
        // El gesto principal de una pantalla (llamar): el mas grande y el unico de su vista.
        lg: "min-h-14 px-8 text-lead",
      },
    },
    defaultVariants: { variant: "primary", size: "default" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  /** Dibuja el hijo (un enlace) con el aspecto del boton, sin envolverlo. */
  readonly asChild?: boolean;
  /** Cargando: el boton queda ocupado y no admite un segundo clic. */
  readonly loading?: boolean;
  /** Error: el boton se marca como invalido. */
  readonly invalid?: boolean;
  readonly ref?: Ref<HTMLButtonElement>;
}

export function Button({
  className,
  variant,
  size,
  asChild = false,
  loading = false,
  invalid = false,
  disabled,
  children,
  type,
  ...props
}: ButtonProps) {
  const clases = cn(buttonVariants({ variant, size }), className);
  if (asChild) {
    return (
      <Slot className={clases} data-invalid={invalid || undefined} {...props}>
        {children}
      </Slot>
    );
  }
  return (
    <button
      type={type ?? "button"}
      className={clases}
      disabled={disabled === true || loading}
      aria-busy={loading || undefined}
      data-invalid={invalid || undefined}
      {...props}
    >
      {loading ? (
        <CircleNotchIcon
          aria-hidden="true"
          focusable="false"
          size={20}
          className="motion-safe:animate-spin"
        />
      ) : null}
      {children}
    </button>
  );
}
