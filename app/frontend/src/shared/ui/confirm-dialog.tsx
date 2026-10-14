// Una ventana modal para confirmar un gesto: titulo, una frase y dos botones.
//
// Es el `<dialog>` del navegador, como los paneles de documentos y de pensamiento:
// `showModal()` atrapa el foco, cierra con Escape y deja inerte lo de atras. Lo que
// aporta este componente es lo que esas ventanas repiten a mano: bloquear el
// desplazamiento de la pagina, devolver el foco al boton que la abrio, y entrar con
// un fundido y una escala corta (sin animar con movimiento reducido).
//
// El foco inicial cae en el primer boton, "Cancelar": lo seguro es lo que queda a mano.
// Mientras `pending`, ni Escape ni los botones la cierran: el gesto ya esta en curso.

import { useEffect, useId, useRef, type ReactNode } from "react";

import { Button } from "./button";
import { cn } from "./cn";
import { lockPageScroll } from "./scroll-lock";

export interface ConfirmDialogProps {
  readonly open: boolean;
  readonly title: string;
  /** Una frase: lo que pasa de verdad al confirmar. */
  readonly description: string;
  readonly cancelLabel: string;
  readonly confirmLabel: string;
  /** Cancelar, Escape: quien la abrio la cierra. */
  readonly onCancel: () => void;
  readonly onConfirm: () => void;
  /** El gesto ya esta en curso: los botones esperan y Escape no cierra. */
  readonly pending?: boolean;
  /** Decorativo, sobre el titulo; el titulo ya dice de que se trata. */
  readonly icon?: ReactNode;
  readonly testId?: string;
}

export function ConfirmDialog({
  open,
  title,
  description,
  cancelLabel,
  confirmLabel,
  onCancel,
  onConfirm,
  pending = false,
  icon,
  testId,
}: ConfirmDialogProps) {
  const ventana = useRef<HTMLDialogElement>(null);
  // El elemento que tenia el foco al abrir, para devolverle el foco al cerrar.
  const volverA = useRef<HTMLElement | null>(null);
  // Lo que dice `open` ahora: Escape cierra el `<dialog>` sin pasar por la prop, y
  // el evento `close` tiene que distinguir esa salida de la que provoca `open=false`.
  const pedida = useRef(open);
  const idTitulo = useId();
  const idDescripcion = useId();

  useEffect(() => {
    pedida.current = open;
    const dialogo = ventana.current;
    if (dialogo === null) {
      return;
    }
    if (open && !dialogo.open) {
      volverA.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialogo.showModal();
    } else if (!open && dialogo.open) {
      dialogo.close();
    }
  }, [open]);

  // Mientras esta abierta, la pagina de atras no se mueve.
  useEffect(() => (open ? lockPageScroll() : undefined), [open]);

  return (
    <dialog
      ref={ventana}
      aria-labelledby={idTitulo}
      aria-describedby={idDescripcion}
      data-testid={testId}
      onCancel={(evento) => {
        if (pending) {
          evento.preventDefault();
        }
      }}
      onClose={() => {
        if (pedida.current) {
          onCancel();
        }
        volverA.current?.focus();
        volverA.current = null;
      }}
      className={cn(
        "m-auto w-[min(26rem,calc(100vw-2rem))] rounded-surface border border-hairline bg-page p-0 text-fg shadow-raised",
        "backdrop:bg-scrim",
        "motion-safe:open:animate-[ut-dialog-in_200ms_var(--ease-out)] motion-safe:backdrop:animate-[ut-fade-in_200ms_var(--ease-out)]",
      )}
    >
      <div className="flex flex-col gap-6 p-5 tablet:p-6">
        <div className="flex flex-col gap-3">
          {icon === undefined ? null : (
            <span
              aria-hidden="true"
              className="flex size-10 items-center justify-center rounded-pill bg-tenant/15 text-tenant"
            >
              {icon}
            </span>
          )}
          <h2 id={idTitulo} className="text-title font-medium text-balance text-fg">
            {title}
          </h2>
          <p id={idDescripcion} className="text-body text-pretty text-fg-secondary">
            {description}
          </p>
        </div>
        <div className="flex flex-col-reverse gap-2 tablet:flex-row tablet:justify-end">
          <Button variant="secondary" disabled={pending} onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant="tenant" loading={pending} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
