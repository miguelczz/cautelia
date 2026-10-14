// El menu de la barra en telefono (decision de Miguel, 2026-10-08): por debajo de
// tableta la navegacion, los dos selectores y el icono de la landing bajaban en
// cuatro filas (~240 px) encima del chat. Ahora la barra es una sola fila --la marca y
// este boton-- y lo demas se abre en un panel bajo ella.
//
// El panel no es una copia: son **los mismos nodos** que en tableta y escritorio
// forman la barra (`Frame`), y el CSS decide si se ven en fila o en el panel. Asi no
// hay dos navegaciones en el arbol de accesibilidad ni dos listas que mantener.
//
// Es una divulgacion, no una ventana modal: el boton dice si esta abierto
// (`aria-expanded`) y que abre (`aria-controls`); al abrir, el foco entra al panel; con
// Escape se cierra y el foco vuelve al boton; tocar fuera, seguir un enlace o sacar el
// foco del panel tambien lo cierran.

import { ListIcon, XIcon } from "@phosphor-icons/react";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent,
  type MouseEvent,
  type Ref,
} from "react";

import { useLocale } from "../../shared/i18n/locale-provider";
import { cn } from "../../shared/ui/cn";
import { lockPageScroll } from "../../shared/ui/scroll-lock";

/** Desde tableta (`--breakpoint-tablet`) la barra vuelve a ser fila y el menu sobra. */
const DESDE_TABLETA = "(min-width: 48rem)";
// Lo primero que puede recibir el foco: un enlace o la opcion elegida de un selector
// (las demas opciones tienen `tabindex="-1"`).
const ENFOCABLE = "a[href], button:not([tabindex='-1']):not([disabled])";

export function usePhoneMenu() {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const close = useCallback((devolverFoco: boolean) => {
    setOpen(false);
    if (devolverFoco) {
      buttonRef.current?.focus();
    }
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }
    panelRef.current?.querySelector<HTMLElement>(ENFOCABLE)?.focus();
    const desbloquear = lockPageScroll();

    const alTeclear = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") {
        evento.preventDefault();
        close(true);
      }
    };
    const alTocar = (evento: PointerEvent) => {
      const destino = evento.target;
      const dentro =
        destino instanceof Node &&
        (panelRef.current?.contains(destino) === true ||
          buttonRef.current?.contains(destino) === true);
      if (!dentro) {
        close(false);
      }
    };
    // Si la ventana crece hasta tableta con el menu abierto, el panel vuelve a ser fila:
    // se cierra para no dejar la pagina bloqueada.
    const medida =
      typeof window.matchMedia === "function" ? window.matchMedia(DESDE_TABLETA) : null;
    const alCrecer = (evento: MediaQueryListEvent) => {
      if (evento.matches) {
        close(false);
      }
    };

    document.addEventListener("keydown", alTeclear);
    document.addEventListener("pointerdown", alTocar);
    medida?.addEventListener("change", alCrecer);
    return () => {
      desbloquear();
      document.removeEventListener("keydown", alTeclear);
      document.removeEventListener("pointerdown", alTocar);
      medida?.removeEventListener("change", alCrecer);
    };
  }, [open, close]);

  const panelProps = {
    id: panelId,
    ref: panelRef,
    "data-open": open ? "true" : "false",
    // Seguir un enlace cierra el menu, tambien si la navegacion no recarga la pagina.
    onClick: (evento: MouseEvent<HTMLDivElement>) => {
      if (open && evento.target instanceof Element && evento.target.closest("a") !== null) {
        close(false);
      }
    },
    // El foco salio del panel hacia otro lugar que no es el boton: se cierra sin
    // moverlo de donde la persona lo llevo.
    onBlur: (evento: FocusEvent<HTMLDivElement>) => {
      const siguiente = evento.relatedTarget;
      if (
        open &&
        siguiente instanceof Node &&
        !evento.currentTarget.contains(siguiente) &&
        buttonRef.current?.contains(siguiente) !== true
      ) {
        close(false);
      }
    },
  };

  return {
    open,
    toggle: () => {
      setOpen((abierto) => !abierto);
    },
    buttonRef,
    panelProps,
  };
}

interface MenuButtonProps {
  readonly open: boolean;
  readonly controls: string;
  readonly onToggle: () => void;
  readonly buttonRef: Ref<HTMLButtonElement>;
  readonly className?: string;
}

/** El boton que abre el menu: la misma forma que los selectores y los enlaces. */
export function MenuButton({ open, controls, onToggle, buttonRef, className }: MenuButtonProps) {
  const { t } = useLocale();
  const Icono = open ? XIcon : ListIcon;
  return (
    <button
      ref={buttonRef}
      type="button"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onToggle}
      data-testid="menu-button"
      className={cn(
        "inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center gap-2 rounded-button border px-3.5",
        "font-mono text-caption tracking-wide whitespace-nowrap",
        "transition-colors duration-[160ms] ease-out",
        // Abierto, lleva el tinte de "elegido", como lo activo del resto de la barra.
        open
          ? "border-transparent bg-selected font-medium text-fg"
          : "border-transparent text-fg hover:bg-surface-alt",
        className,
      )}
    >
      <Icono aria-hidden="true" focusable="false" size={16} />
      {t("shell.menu.button")}
    </button>
  );
}
