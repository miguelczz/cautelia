// La espera de que el proceso este listo (ReadinessWatch; functional-spec 2.1,
// BR5.4, AC5.16.4).
//
//   checking --listo 200--> ready
//   checking --503 o sin respuesta--> waking
//   waking --listo 200--> ready
//   waking --5 s y sigue sin 200--> waking (otra consulta)
//   waking --60 s desde started_at--> unavailable
//   unavailable --"Reintentar"--> checking
//   ready --una llamada pierde la conexion--> checking
//
// La maquina es una funcion pura (`reduceReadiness`) y el gancho solo pone los
// relojes y las consultas; asi las pruebas recorren los tres caminos con un
// reloj simulado, sin esperar de verdad (NFR16.5).

import { useCallback, useEffect, useReducer } from "react";

import { onConnectivityLost } from "./connectivity";
import { checkReady, type ReadyOutcome } from "./site";

/** Entre una consulta y la siguiente, mientras despierta. */
export const POLL_INTERVAL_MS = 5_000;
/** Desde que empezo la espera hasta "no disponible". */
export const GIVE_UP_AFTER_MS = 60_000;
/**
 * Cuanto puede tardar una consulta antes de contarla como "sin respuesta". Menos
 * que el intervalo, para que dos consultas nunca se solapen.
 */
export const ATTEMPT_TIMEOUT_MS = 4_000;
export type ReadinessState = "checking" | "ready" | "waking" | "unavailable";

export interface ReadinessWatch {
  readonly state: ReadinessState;
  /** Cuando empezo esta espera, en milisegundos del reloj de la pagina. */
  readonly startedAt: number;
  /** Cuantas consultas fallidas lleva. */
  readonly attempts: number;
  /** La ruta que pidio la persona, para devolverla ahi al despertar. */
  readonly requestedRoute: string;
}

export type ReadinessEvent =
  | { readonly type: "ready" }
  | { readonly type: "not_ready"; readonly now: number }
  | { readonly type: "tick"; readonly now: number }
  | { readonly type: "retry"; readonly now: number }
  | { readonly type: "connectivity_lost"; readonly now: number };

export function startReadiness(now: number, requestedRoute: string): ReadinessWatch {
  return { state: "checking", startedAt: now, attempts: 0, requestedRoute };
}

function vencida(watch: ReadinessWatch, now: number): boolean {
  return now - watch.startedAt >= GIVE_UP_AFTER_MS;
}

/** La transicion. Un evento que no aplica al estado actual no cambia nada. */
export function reduceReadiness(watch: ReadinessWatch, event: ReadinessEvent): ReadinessWatch {
  switch (event.type) {
    case "ready":
      return watch.state === "checking" || watch.state === "waking"
        ? { ...watch, state: "ready" }
        : watch;
    case "not_ready":
      if (watch.state !== "checking" && watch.state !== "waking") {
        return watch;
      }
      return {
        ...watch,
        state: vencida(watch, event.now) ? "unavailable" : "waking",
        attempts: watch.attempts + 1,
      };
    case "tick":
      return watch.state === "waking" && vencida(watch, event.now)
        ? { ...watch, state: "unavailable" }
        : watch;
    case "retry":
      return watch.state === "unavailable"
        ? { ...startReadiness(event.now, watch.requestedRoute) }
        : watch;
    case "connectivity_lost":
      return watch.state === "ready"
        ? { ...startReadiness(event.now, watch.requestedRoute) }
        : watch;
  }
}

export interface ReadinessDeps {
  /** Una consulta de listo. Por omision, `GET /api/health/ready`. */
  readonly check?: (signal: AbortSignal) => Promise<ReadyOutcome>;
  /** El reloj. Por omision, `Date.now`, que el reloj simulado de las pruebas controla. */
  readonly now?: () => number;
}

export interface Readiness {
  readonly watch: ReadinessWatch;
  /** "Reintentar" desde "no disponible". */
  readonly retry: () => void;
}

function rutaPedida(): string {
  return `${window.location.pathname}${window.location.search}`;
}

/** La espera de "listo", con sus relojes y sus consultas. */
export function useReadiness({
  check = checkReady,
  now = Date.now,
}: ReadinessDeps = {}): Readiness {
  const [watch, dispatch] = useReducer(reduceReadiness, undefined, () =>
    startReadiness(now(), rutaPedida()),
  );

  // Una consulta al entrar en "comprobando" y otra cada cinco segundos mientras
  // despierta. Cada una con su tiempo maximo, y cancelada si el estado cambia.
  useEffect(() => {
    if (watch.state !== "checking" && watch.state !== "waking") {
      return undefined;
    }
    let vigente = true;
    const control = new AbortController();

    const consultar = () => {
      const limite = setTimeout(() => {
        control.abort(new DOMException("readiness attempt timed out", "TimeoutError"));
      }, ATTEMPT_TIMEOUT_MS);
      check(control.signal)
        .catch(() => "not_ready" as const)
        .then((resultado) => {
          clearTimeout(limite);
          if (vigente) {
            dispatch(resultado === "ready" ? { type: "ready" } : { type: "not_ready", now: now() });
          }
        })
        .catch((error: unknown) => {
          console.error("untangle: the readiness check could not be recorded", error);
        });
    };

    const espera = watch.state === "checking" ? 0 : POLL_INTERVAL_MS;
    const siguiente = setTimeout(consultar, espera);
    return () => {
      vigente = false;
      clearTimeout(siguiente);
      control.abort();
    };
  }, [watch.state, watch.attempts, check, now]);

  // Los sesenta segundos cuentan desde que empezo la espera, no desde la ultima
  // consulta: sin este reloj, una consulta colgada los alargaria.
  useEffect(() => {
    if (watch.state !== "waking") {
      return undefined;
    }
    const restante = Math.max(0, watch.startedAt + GIVE_UP_AFTER_MS - now());
    const reloj = setTimeout(() => {
      dispatch({ type: "tick", now: now() });
    }, restante);
    return () => {
      clearTimeout(reloj);
    };
  }, [watch.state, watch.startedAt, now]);

  // Una llamada que pierde la conexion devuelve la espera a "comprobando".
  useEffect(
    () =>
      onConnectivityLost(() => {
        dispatch({ type: "connectivity_lost", now: now() });
      }),
    [now],
  );

  const retry = useCallback(() => {
    dispatch({ type: "retry", now: now() });
  }, [now]);

  return { watch, retry };
}
