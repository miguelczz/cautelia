// El estado de la vista de comparacion, como logica pura (entidad `ComparisonColumn`).
//
// **Un estado por columna y ninguno para la vista** (BR2.2): con uno global, una
// columna no podria aparecer mientras otra carga. Cada columna cambia solo por
// su propio resultado.
//
// `failed` y `rejected` son estados distintos a proposito: "no se pudo revisar la
// poliza" se arregla en el proveedor y "se alcanzo un limite" en la cuota.
// Colapsarlos es el defecto que el proyecto persigue en todas partes.

import type { MessageRejected } from "../../shared/api-client/chat";
import type { TenantPresentation } from "../../shared/api-client/site";
import type { Locale } from "../../shared/copy/copy-keys";
import type { WireCitation } from "../chat/chat-events";

/**
 * Lo que una aseguradora contesto. "No encuentro una clausula" es un resultado
 * verificado y **no** es un fallo: por eso es un valor propio y no una lista de
 * citas vacia.
 */
export type ColumnAnswer =
  | {
      readonly kind: "cited";
      readonly language: Locale;
      readonly text: string;
      readonly citations: readonly WireCitation[];
    }
  | { readonly kind: "no_clause"; readonly language: Locale };

/** Lo que devuelve preguntarle a una aseguradora. */
export type ColumnOutcome =
  | { readonly kind: "answered"; readonly answer: ColumnAnswer }
  | {
      readonly kind: "rejected";
      readonly limit: MessageRejected["limit"];
      readonly copyKey: string;
    }
  /**
   * El texto no es una pregunta de cobertura, y lo dice **el servidor** (Q3): el
   * mismo reconocedor determinista que decide si un primer mensaje abre una
   * consulta o un siniestro. No es un estado de columna --no hay nada que esa
   * columna pueda mostrar-- y es el mismo para las tres, porque las tres preguntan
   * lo mismo en el mismo idioma: la vista lo dice una vez.
   */
  | { readonly kind: "out_of_scope"; readonly copyKey: string }
  /**
   * La demostracion no acepta casos nuevos (BR3.2 de U20). Como el de arriba, no
   * es un estado de columna --no hay nada que esa columna pueda mostrar-- y es el
   * mismo para las tres: la vista lo dice una vez. Y a diferencia de aquel, **no
   * ofrece el chat**: el chat se estrecha igual, asi que mandar alli a quien
   * pregunta seria mandarlo a la misma puerta cerrada.
   */
  | { readonly kind: "demo_closed"; readonly copyKey: string }
  | { readonly kind: "failed" };

export type ColumnView =
  | { readonly state: "idle" }
  | { readonly state: "loading" }
  | { readonly state: "answered"; readonly answer: ColumnAnswer }
  | { readonly state: "failed" }
  /**
   * La pagina se recargo (o se cerro) antes de que esta columna respondiera, y la
   * respuesta ya no tiene por donde llegar. Es un estado propio y no `failed`:
   * la poliza no fallo, lo que se perdio fue la espera. Solo nace al restaurar lo
   * guardado, nunca de una respuesta del servidor.
   */
  | { readonly state: "interrupted" }
  | {
      readonly state: "rejected";
      readonly limit: MessageRejected["limit"];
      readonly copyKey: string;
    };

export type ColumnState = ColumnView["state"];

export type ComparisonColumn = ColumnView & { readonly tenantId: string };

/** La marca de una aseguradora tal como la sirve el directorio del sitio. */
export type ComparisonBrand = NonNullable<TenantPresentation["brand"]>;

/** Una aseguradora tal como la describe la vista. */
export interface ComparisonInsurer {
  readonly tenantId: string;
  readonly displayName: string;
  readonly kind: "carrier" | "agency";
  readonly examplePolicy: string;
  /** Quien emitio la poliza de ejemplo. Una agencia no emite (BR1.2). */
  readonly issuedBy: string | null;
  /** Su acento y su monograma; sin marca, la columna usa los de Cautelia. */
  readonly brand: ComparisonBrand | null;
}

/** Manda la pregunta a una aseguradora. Nunca debe lanzar; si lo hace, es `failed`. */
export type AskInsurer = (tenantId: string, question: string) => Promise<ColumnOutcome>;

/**
 * La divulgacion esta completa cuando cada agencia nombra a su emisora (BR1.1,
 * BR1.2). Sin eso no se ofrece la pregunta: una poliza de agencia sin emisor
 * afirma algo que no es.
 */
export function disclosureComplete(insurers: readonly ComparisonInsurer[]): boolean {
  return (
    insurers.length > 0 &&
    insurers.every((aseguradora) => aseguradora.kind !== "agency" || aseguradora.issuedBy !== null)
  );
}

export function idleColumns(insurers: readonly ComparisonInsurer[]): readonly ComparisonColumn[] {
  return insurers.map((aseguradora) => ({ tenantId: aseguradora.tenantId, state: "idle" }));
}

/** Una pregunta nueva: las tres columnas pasan a cargar. */
export function startQuestion(columns: readonly ComparisonColumn[]): readonly ComparisonColumn[] {
  return columns.map((columna) => ({ tenantId: columna.tenantId, state: "loading" }));
}

/** Volver a preguntar solo a las columnas dadas; las demas conservan lo que tienen. */
export function startColumns(
  columns: readonly ComparisonColumn[],
  tenantIds: readonly string[],
): readonly ComparisonColumn[] {
  return columns.map((columna): ComparisonColumn =>
    tenantIds.includes(columna.tenantId)
      ? { tenantId: columna.tenantId, state: "loading" }
      : columna,
  );
}

/**
 * Lo guardado vuelve a la pagina. Una columna que estaba cargando solo sigue
 * cargando si su pregunta todavia esta en vuelo en esta misma pestana (la persona
 * salio y volvio sin recargar); si no, su respuesta ya no puede llegar y se dice.
 */
export function restoreColumns(
  columns: readonly ComparisonColumn[],
  isInFlight: (tenantId: string) => boolean,
): readonly ComparisonColumn[] {
  return columns.map((columna): ComparisonColumn =>
    columna.state === "loading" && !isInFlight(columna.tenantId)
      ? { tenantId: columna.tenantId, state: "interrupted" }
      : columna,
  );
}

/** El resultado de **una** columna; las otras quedan como estaban. */
export function settleColumn(
  columns: readonly ComparisonColumn[],
  tenantId: string,
  outcome: ColumnOutcome,
): readonly ComparisonColumn[] {
  return columns.map((columna): ComparisonColumn => {
    if (columna.tenantId !== tenantId) {
      return columna;
    }
    switch (outcome.kind) {
      case "answered":
        return { tenantId, state: "answered", answer: outcome.answer };
      case "rejected":
        return { tenantId, state: "rejected", limit: outcome.limit, copyKey: outcome.copyKey };
      case "failed":
        return { tenantId, state: "failed" };
      case "out_of_scope":
        // Vuelve a `idle`: la pregunta no se admitio, asi que esta columna no tiene
        // nada que mostrar. Dibujarla como `failed` diria que la poliza no se pudo
        // revisar, y lo que paso es que no se pregunto por una cobertura.
        return { tenantId, state: "idle" };
      case "demo_closed":
        // Lo mismo y por lo mismo: la pregunta no se admitio. La diferencia con
        // la de arriba esta en lo que la vista dice, no en lo que la columna
        // muestra.
        return { tenantId, state: "idle" };
    }
  });
}

export function anyLoading(columns: readonly ComparisonColumn[]): boolean {
  return columns.some((columna) => columna.state === "loading");
}
