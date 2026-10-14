// Aviso en linea: un mensaje que se lee en su sitio, sin tapar la pantalla.
//
// No es una region en vivo por su cuenta: si hay que anunciarlo, lo anuncia quien
// lo muestra por el anunciador compartido (BR7.5). El tono lleva icono y texto,
// nunca solo color (BR7.6), y sale de los tokens semanticos, nunca del acento de
// una aseguradora (BR1.6).

import {
  CheckCircleIcon,
  InfoIcon,
  WarningCircleIcon,
  WarningIcon,
  type Icon,
} from "@phosphor-icons/react";
import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";

export const inlineAlertVariants = cva(
  "flex items-start gap-3 rounded-surface border bg-surface p-4 text-body text-fg",
  {
    variants: {
      tone: {
        info: "border-hairline",
        success: "border-success",
        warning: "border-warning",
        danger: "border-danger",
      },
    },
    defaultVariants: { tone: "info" },
  },
);

type Tone = "info" | "success" | "warning" | "danger";

/** El icono y su color de cada tono. */
function toneIcon(tone: Tone): { readonly Icono: Icon; readonly color: string } {
  switch (tone) {
    case "info":
      return { Icono: InfoIcon, color: "text-fg-secondary" };
    case "success":
      return { Icono: CheckCircleIcon, color: "text-success" };
    case "warning":
      return { Icono: WarningIcon, color: "text-warning" };
    case "danger":
      return { Icono: WarningCircleIcon, color: "text-danger" };
  }
}

export interface InlineAlertProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "title">, VariantProps<typeof inlineAlertVariants> {
  /** Una accion junto al mensaje, por ejemplo "Reintentar". */
  readonly action?: ReactNode;
}

export function InlineAlert({ className, tone, action, children, ...props }: InlineAlertProps) {
  const tono = tone ?? "info";
  const { Icono, color } = toneIcon(tono);
  return (
    <div
      className={cn(
        inlineAlertVariants({ tone: tono }),
        // Con una accion al lado el icono, el texto y el boton se centran en un mismo eje: con
        // una sola linea de texto, el icono arriba y el texto centrado contra el boton de 44 px
        // quedaban desalineados. Sin accion (o apilados, en telefono) el icono se queda arriba,
        // con la primera linea.
        action !== undefined && action !== null && "tablet:items-center",
        className,
      )}
      {...props}
    >
      <Icono
        aria-hidden="true"
        focusable="false"
        size={24}
        className={cn(
          "mt-px shrink-0",
          action !== undefined && action !== null && "tablet:mt-0",
          color,
        )}
      />
      <div className="flex min-w-0 flex-1 flex-col gap-3 tablet:flex-row tablet:items-center tablet:justify-between">
        <div className="min-w-0">{children}</div>
        {action}
      </div>
    </div>
  );
}
