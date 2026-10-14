// La costura de la comparacion con el servidor (U23, tanda 2).
//
// **Ninguna ruta nueva** (FD-U23-1): la vista habla tres veces por las rutas del
// chat que ya existen, una por aseguradora, y abre tres conversaciones. De ahi
// salen gratis tres cosas que de otro modo serian reglas que alguien tiene que
// cumplir: el aislamiento por columna, que cada pregunta cuente como tres contra
// los limites, y la carga y el fallo por columna.
//
// El flujo se abre **antes** de mandar el mensaje, y no es una preferencia: sin
// flujo abierto el servidor admite el mensaje y no lo entrega, porque no hay cola
// donde publicar la respuesta. Y la galleta del visitante la entrega el flujo.
//
// **"Antes" es que ya abrio, no que ya se creo** (2026-10-10). Crear el
// `EventSource` no espera a nadie: el mensaje podia llegar al servidor primero, se
// perdia, y la columna se quedaba en "Revisando" para siempre. Y con las tres
// columnas abriendo a la vez en un navegador sin galleta, cada flujo recibia una
// galleta distinta y dos de las tres preguntas iban a una conversacion sin flujo.
// Por eso la primera apertura va sola y las demas la esperan.

import type { Locale } from "../../shared/copy/copy-keys";
import { openChatStream, sendMessage } from "../../shared/api-client/chat";
import type { TenantPresentation } from "../../shared/api-client/site";
import type { WireEvent } from "../chat/chat-events";
import type { ColumnOutcome } from "./comparison-state";

/**
 * Quien emitio la poliza de ejemplo de una agencia, o `null`.
 *
 * Sale del contrato: `example_policy_issuer` viaja en `GET /api/site` ya resuelto
 * a nombre visible, porque el servidor es el unico que tiene las tres
 * aseguradoras a la vista. Aqui no se adivina nada y no se cruza ninguna fila: lo
 * que el directorio no trae no se muestra, y entonces la divulgacion queda
 * incompleta y la vista no ofrece la pregunta (BR1.2).
 */
export const exampleIssuerName = (tenant: TenantPresentation): string | null =>
  tenant.example_policy_issuer ?? null;

/**
 * Lo que una respuesta de cobertura significa para una columna, o `null` si el mensaje
 * no es la respuesta todavia.
 *
 * Desde la fase 1 (2026-10-08) la pregunta cierra su turno con "dejeme revisar su
 * poliza" y la respuesta llega despues, sola, con su resultado explicito. Los dos no
 * se confunden: "no encuentro una clausula" es un resultado verificado y "no pude
 * verificar" es un fallo, y colapsarlos contaminaria una metrica publicada.
 */
function _respuesta(evento: Extract<WireEvent, { kind: "turn.final" }>): ColumnOutcome | null {
  switch (evento.coverage_outcome) {
    case undefined:
    case null:
      return null;
    case "verified":
      return evento.citations.length > 0
        ? {
            kind: "answered",
            answer: {
              kind: "cited",
              language: evento.language,
              text: evento.text,
              citations: evento.citations,
            },
          }
        : { kind: "failed" };
    case "no_clause_found":
      return { kind: "answered", answer: { kind: "no_clause", language: evento.language } };
    default:
      return { kind: "failed" };
  }
}

/**
 * Espera la respuesta cerrada de una conversacion por su flujo.
 *
 * **Sin plazo propio.** Cada camino de fallo del servidor publica algo --el turno
 * roto publica su error antes de relanzar-- asi que un plazo aqui solo podria
 * cortar una respuesta que venia en camino. Lo que si cierra la espera es que el
 * flujo se caiga, y eso lo dice `onerror`.
 */
function _esperarRespuesta(flujo: EventSource): Promise<ColumnOutcome> {
  return new Promise<ColumnOutcome>((resolver) => {
    flujo.onmessage = (evento: MessageEvent<string>) => {
      const cable = JSON.parse(evento.data) as WireEvent;
      switch (cable.kind) {
        case "turn.final": {
          // La frase de espera tambien llega como `turn.final`: se sigue esperando
          // hasta la respuesta, que es la que trae su resultado.
          const respuesta = _respuesta(cable);
          if (respuesta !== null) {
            resolver(respuesta);
          }
          break;
        }
        case "turn.error":
          resolver({ kind: "failed" });
          break;
        case "turn.handoff":
          // Una derivacion a una persona no es una respuesta que comparar, y esta
          // vista no tiene estado para "alguien lo esta revisando": inventarlo es
          // trabajo de diseno que esta tanda no hace. Lo que el visitante lee es
          // "no se pudo revisar la poliza", que es lo que de verdad pasa con la
          // comparacion de esa columna.
          resolver({ kind: "failed" });
          break;
        default:
          // `turn.partial` y `turn.waiting` no cierran el turno: se sigue esperando.
          break;
      }
    };
    flujo.onerror = () => {
      resolver({ kind: "failed" });
    };
  });
}

/** El estado `OPEN` de un `EventSource`, por su valor: en las pruebas no hay clase. */
const ABIERTO = 1;

/**
 * Cuanto se espera, como mucho, una respuesta. Cada camino de fallo del servidor
 * publica algo, asi que esto no deberia vencer nunca; existe para que, si algo se
 * pierde, la columna diga que no se pudo en vez de girar para siempre.
 */
export const PLAZO_DE_RESPUESTA_MS = 60_000;

/** Resuelve cuando el flujo esta abierto de verdad: el servidor ya tiene su cola. */
function _abierto(flujo: EventSource): Promise<void> {
  return new Promise<void>((resolver) => {
    if (flujo.readyState === ABIERTO) {
      resolver();
      return;
    }
    flujo.onopen = () => {
      resolver();
    };
  });
}

/**
 * La primera apertura de esta pagina, que es la que deja puesta la galleta del
 * visitante. Las demas columnas la esperan antes de abrir su flujo.
 */
let primeraApertura: Promise<unknown> | null = null;

/** Solo las pruebas: cada una empieza sin una apertura anterior. */
export function forgetFirstOpening(): void {
  primeraApertura = null;
}

function _vencido(): Promise<ColumnOutcome> {
  return new Promise<ColumnOutcome>((resolver) => {
    window.setTimeout(() => {
      resolver({ kind: "failed" });
    }, PLAZO_DE_RESPUESTA_MS);
  });
}

/** Lo que `askInsurer` necesita saber de la pantalla. */
export interface AskOptions {
  /** El idioma de la pantalla, respaldo cuando el texto no trae senal (BR2.1). */
  readonly locale: Locale;
  /** Solo las pruebas lo cambian: el flujo de verdad lo abre el navegador. */
  readonly openStream?: (tenantId: string) => EventSource;
}

/**
 * Le pregunta a una aseguradora y devuelve lo que esa columna tiene que mostrar.
 *
 * Los cuatro rechazos se distinguen y ninguno es un fallo: el limite trae cual
 * fue, el de fuera de proposito y el de la demo estrechada traen su frase, y el
 * fallo de verdad no trae nada.
 */
export async function askInsurer(
  tenantId: string,
  question: string,
  options: AskOptions,
): Promise<ColumnOutcome> {
  const anterior = primeraApertura;
  if (anterior !== null) {
    await anterior;
  }
  const flujo = (options.openStream ?? openChatStream)(tenantId);
  try {
    // La espera se arma **antes** del envio: armarla despues dejaria una ventana
    // en la que la respuesta llega y nadie la escucha.
    const esperada = _esperarRespuesta(flujo);
    // Abierto de verdad, o caido: un flujo que no abre resuelve `esperada` con su
    // fallo, y entonces no se manda nada.
    const apertura = Promise.race([_abierto(flujo).then(() => true), esperada.then(() => false)]);
    primeraApertura ??= apertura;
    if (!(await apertura)) {
      return await esperada;
    }
    const envio = await sendMessage(tenantId, question, {
      surface: "comparison",
      locale: options.locale,
    });
    switch (envio.outcome) {
      case "rejected":
        return {
          kind: "rejected",
          limit: envio.rejected.limit,
          copyKey: envio.rejected.copy_key,
        };
      case "out_of_scope":
        return { kind: "out_of_scope", copyKey: envio.outOfScope.copy_key };
      case "demo_closed":
        return { kind: "demo_closed", copyKey: envio.closed.copy_key };
      case "failed":
        return { kind: "failed" };
      case "accepted":
        return await Promise.race([esperada, _vencido()]);
    }
  } finally {
    // Una pregunta, un flujo. Dejarlo abierto acumularia tres por pregunta y cada
    // respuesta se veria tantas veces como flujos hubiera.
    flujo.close();
  }
}
