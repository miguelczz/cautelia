// El mensaje de la agente, palabra por palabra **despues de la guardia** (plan 09, punto 4).
//
// Decision de Miguel del 2026-11-02: la respuesta se ve progresivamente, pero solo despues de
// que el texto completo paso la guardia de salida en el servidor. Esta pantalla recibe el
// mensaje ya revisado y entero (`turn.final`); mostrarlo de a poco es solo ritmo de lectura,
// nunca una transmision de lo que el modelo va escribiendo.
//
// **Para quien usa un lector de pantalla el mensaje siempre esta entero.** Mientras se
// revela, el texto completo vive en un elemento solo para lectores y la parte visible se
// oculta de ellos: nadie oye media frase ni la misma palabra repetida. El anuncio en vivo
// (`useAnnouncer`) lo hace la pagina una sola vez con el texto completo, no esta pieza.
//
// **Cuanto tarda:** unos 45 ms por palabra y nunca mas de 1,5 s en total, por largo que sea el
// mensaje: lo largo se revela en grupos de palabras. Con `prefers-reduced-motion` el mensaje
// aparece entero de una vez, igual que el historial recuperado.

import { useEffect, useEffectEvent, useState } from "react";

/** Lo que tarda cada palabra, como mucho. */
export const WORD_MS = 45;
/** Lo que tarda el mensaje entero, como mucho, sea cual sea su largo. */
export const MAX_REVEAL_MS = 1500;
/** Cada cuanto se actualiza lo que se ve. */
const TICK_MS = 30;

/** Si la persona pidio menos movimiento. Sin `matchMedia` (pruebas) se anima. */
export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/** El mensaje partido en palabras y en los espacios entre ellas, sin perder ninguno. */
function tokens(text: string): readonly string[] {
  return text.split(/(\s+)/).filter((trozo) => trozo !== "");
}

function isWord(token: string): boolean {
  return !/^\s+$/.test(token);
}

/** Cuantos milisegundos se le dan a cada palabra de un mensaje con tantas palabras. */
export function msPerWord(words: number): number {
  return Math.min(WORD_MS, MAX_REVEAL_MS / Math.max(words, 1));
}

/** El texto hasta la palabra `shown` (contando solo palabras), con sus espacios. */
function upTo(parts: readonly string[], shown: number): string {
  let vistas = 0;
  let texto = "";
  for (const parte of parts) {
    if (isWord(parte)) {
      if (vistas === shown) {
        break;
      }
      vistas += 1;
    }
    texto += parte;
  }
  return texto;
}

export interface ProgressiveTextProps {
  /** El mensaje entero, ya revisado por la guardia. */
  readonly text: string;
  /** Si se revela de a poco. Falso: el texto sale entero, como cualquier otro. */
  readonly animate: boolean;
  /** Se llama cada vez que lo visible crece, para que la pantalla siga el final. */
  readonly onGrow?: () => void;
  /** Se llama una vez cuando el mensaje ya se ve entero (o enseguida, si no se anima). */
  readonly onDone?: () => void;
}

export function ProgressiveText(props: ProgressiveTextProps) {
  // Un texto distinto es otra revelacion desde cero: la clave la reinicia sin efectos.
  return <Reveal key={props.text} {...props} />;
}

function Reveal({ text, animate, onGrow, onDone }: ProgressiveTextProps) {
  const [reducido] = useState(prefersReducedMotion);
  const partes = tokens(text);
  const total = partes.filter(isWord).length;
  const animar = animate && !reducido && total > 1;
  const [mostradas, setMostradas] = useState(animar ? 0 : total);
  // Los avisos a la pantalla se leen al disparar el efecto, no al dibujar: sin esto un
  // dibujo de la pantalla reiniciaria el reloj.
  const avanzo = useEffectEvent(() => {
    onGrow?.();
  });
  const termino = useEffectEvent(() => {
    onDone?.();
  });

  useEffect(() => {
    if (!animar) {
      termino();
      return;
    }
    const porPalabra = msPerWord(total);
    const inicio = Date.now();
    const intervalo = window.setInterval(() => {
      const quedan = Math.min(total, Math.floor((Date.now() - inicio) / porPalabra) + 1);
      setMostradas(quedan);
      avanzo();
      if (quedan >= total) {
        window.clearInterval(intervalo);
        termino();
      }
    }, TICK_MS);
    return () => {
      window.clearInterval(intervalo);
    };
  }, [animar, total]);

  if (!animar || mostradas >= total) {
    return <>{text}</>;
  }
  return (
    <>
      {/* El mensaje entero para quien lo lee con un lector de pantalla. */}
      <span className="sr-only">{text}</span>
      <span aria-hidden="true" data-testid="chat-progressive">
        {upTo(partes, mostradas)}
      </span>
    </>
  );
}
