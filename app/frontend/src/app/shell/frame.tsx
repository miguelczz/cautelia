// El marco de toda pantalla: el enlace para saltar al contenido, la barra
// superior con la marca, la navegacion, los dos selectores y lo que va al extremo, el
// contenido y, si lo hay, el pie. En telefono la barra es la marca y un boton de menu
// que abre lo demas en un panel (decision de Miguel, 2026-10-08).
//
// Lo usan las dos ramas de la aplicacion: la espera del proceso, que se dibuja
// **antes** del enrutador, y el marco del enrutador. Asi los dos selectores estan
// en todas las pantallas, tambien mientras la demo carga
// (accessibility-checklist.md, seccion 1).

import type { ReactNode } from "react";

import { cn } from "../../shared/ui/cn";
import { LanguageSelector } from "./language-selector";
import { MenuButton, usePhoneMenu } from "./phone-menu";
import { MAIN_CONTENT_ID, SkipLink } from "./skip-link";
import { ThemeToggle } from "./theme-toggle";

interface FrameProps {
  /** La marca, que lleva al inicio. */
  readonly brand: ReactNode;
  /** Los botones de navegacion, a la derecha de la barra, junto a los selectores. */
  readonly nav?: ReactNode;
  /** Lo que va en el extremo derecho de la barra, despues de los selectores. */
  readonly trailing?: ReactNode;
  readonly footer?: ReactNode;
  /**
   * Si la pantalla **llena la vista** en vez de crecer con su contenido (decision
   * de Miguel, 2026-10-06, para el chat): la barra y el contenido caben en la
   * ventana, sin pie, y lo unico que se desplaza es lo que la pantalla decida por
   * dentro --la conversacion--, nunca la pagina (`styles.css` lo asegura en `html`). Lo declara la ruta en su
   * `staticData` y lo lee el marco del enrutador.
   */
  readonly fill?: boolean;
  /**
   * Si la pantalla **cabe en una sola vista en un computador con espacio**
   * (variante `roomy`): el marco mide la ventana y centra el contenido entre la
   * barra y el pie. En telefono y tablet fluye y se desplaza como siempre; y si
   * el contenido no cabe, se desplaza dentro de `main` y nunca se recorta. Lo
   * declara la ruta en su `staticData`.
   */
  readonly onePage?: boolean;
  /**
   * Si el proceso todavia esta respondiendo: un hilo fino bajo la barra que avanza y
   * vuelve, para decir "sigue en marcha" sin explicar por que (decision de Miguel,
   * 2026-10-06). Con movimiento reducido no se dibuja y queda el esqueleto.
   */
  readonly busy?: boolean;
  readonly children: ReactNode;
}

export function Frame({
  brand,
  nav,
  trailing,
  footer,
  fill = false,
  onePage = false,
  busy = false,
  children,
}: FrameProps) {
  const menu = usePhoneMenu();
  return (
    <div
      data-fill-view={fill ? "" : undefined}
      className={cn(
        "flex flex-col bg-page text-fg",
        fill ? "h-dvh overflow-hidden" : "min-h-dvh",
        !fill && onePage && "roomy:h-dvh roomy:overflow-hidden",
      )}
    >
      <SkipLink />
      {/* En telefono, con el menu abierto, lo de detras se oscurece y tocarlo lo cierra.
          Fuera de la cabecera: su `backdrop-blur` volveria a la cabecera el marco de
          referencia de lo `fixed`. */}
      {menu.open ? (
        <div
          aria-hidden="true"
          data-testid="menu-scrim"
          className="fixed inset-0 z-30 bg-scrim tablet:hidden motion-safe:transition-opacity motion-safe:duration-200 motion-safe:starting:opacity-0"
        />
      ) : null}
      <header className="sticky top-0 z-40 border-b border-hairline bg-bar/85 backdrop-blur-md">
        {/* En escritorio, una sola linea: la marca a la izquierda y, a la derecha, la
            navegacion, los dos selectores y --al final-- lo que va al extremo (el icono de
            volver al sitio). En tableta no caben, y la marca y los selectores quedan arriba
            mientras la navegacion y lo del extremo bajan a su propia fila, alineados a la
            derecha. En telefono la barra es la marca y el boton del menu, y todo lo demas
            se abre en un panel bajo ella (`phone-menu.tsx`). El orden del documento es el
            de escritorio. */}
        <div className="mx-auto grid max-w-content grid-cols-[1fr_auto_auto] items-center gap-x-3 gap-y-1 px-4 py-1 tablet:px-8 desktop:flex">
          <div className="col-start-1 row-start-1 desktop:mr-auto">{brand}</div>
          <MenuButton
            open={menu.open}
            controls={menu.panelProps.id}
            onToggle={menu.toggle}
            buttonRef={menu.buttonRef}
            className="col-start-3 row-start-1 justify-self-end tablet:hidden"
          />
          {/* Desde tableta este contenedor no existe para el dibujo (`contents`): sus
              hijos son celdas de la barra. Por debajo, es el panel del menu. */}
          <div
            {...menu.panelProps}
            className={cn(
              "tablet:contents",
              "max-tablet:absolute max-tablet:inset-x-0 max-tablet:top-full max-tablet:flex-wrap max-tablet:items-center max-tablet:gap-x-3 max-tablet:gap-y-3",
              "max-tablet:border-b max-tablet:border-hairline max-tablet:bg-page max-tablet:px-4 max-tablet:pt-3 max-tablet:pb-4 max-tablet:shadow-raised",
              "max-tablet:motion-safe:transition-[opacity,translate] max-tablet:motion-safe:duration-200 max-tablet:motion-safe:ease-out",
              "max-tablet:motion-safe:starting:-translate-y-1 max-tablet:motion-safe:starting:opacity-0",
              menu.open ? "max-tablet:flex" : "max-tablet:hidden",
            )}
          >
            {nav === undefined || nav === null ? null : (
              <div className="col-start-2 row-start-2 justify-self-end max-tablet:w-full max-tablet:border-b max-tablet:border-hairline max-tablet:pb-3">
                {nav}
              </div>
            )}
            <div className="col-span-2 col-start-2 row-start-1 flex items-center gap-2 justify-self-end">
              <LanguageSelector />
              <ThemeToggle />
            </div>
            {trailing === undefined || trailing === null ? null : (
              <div className="col-start-3 row-start-2 max-tablet:ml-auto">{trailing}</div>
            )}
          </div>
        </div>
        {busy ? (
          <div
            aria-hidden="true"
            data-testid="progress-thread"
            className="absolute inset-x-0 -bottom-px h-0.5 overflow-hidden"
          >
            <div className="ut-thread h-full w-full bg-thread" />
          </div>
        ) : null}
      </header>
      <main
        id={MAIN_CONTENT_ID}
        tabIndex={-1}
        className={cn(
          "flex-1 focus:outline-none",
          fill && "flex min-h-0 flex-col",
          !fill && onePage && "roomy:flex roomy:min-h-0 roomy:flex-col roomy:overflow-y-auto",
        )}
      >
        {children}
      </main>
      {/* Una pantalla que llena la vista no lleva pie en ningun tamano: el chat ocupa
          hasta el borde de abajo (decision de Miguel, 2026-10-08). */}
      {fill ? null : footer}
    </div>
  );
}

/**
 * La clase de la marca, igual con enlace del enrutador o comun.
 *
 * En la fuente del cuerpo y no en la de titulos de la landing, a proposito: la
 * pagina de espera solo carga la del cuerpo, y la de titulos serian 22 KB mas
 * antes del primer pintado, que PERF-U6.1 (200 KB) no admitia el 2026-10-06
 * (medido: 209 KB con ella). Lo que hace que la marca se lea como la de la
 * landing es el simbolo que va al lado, que pesa medio kilobyte.
 */
export const BRAND_CLASSES =
  "inline-flex min-h-11 items-center gap-2.5 rounded-control font-body text-lead font-medium tracking-tight text-fg no-underline";
