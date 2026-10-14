// Como se escriben las cifras del tablero de gasto.
//
// Una llamada cuesta fracciones de centavo y el total del proyecto, centavos: con
// dos decimales fijos casi todo se leeria como cero. Los decimales crecen cuando la
// cifra es chica, y nunca mas de seis.

import type { SpendTotal, UnpricedUsage } from "../../shared/api-client/spend";
import { useLocale } from "../../shared/i18n/locale-provider";

function decimales(valor: number): number {
  const absoluto = Math.abs(valor);
  if (absoluto === 0 || absoluto >= 1) {
    return 2;
  }
  if (absoluto >= 0.1) {
    return 3;
  }
  if (absoluto >= 0.01) {
    return 4;
  }
  return 6;
}

/** Un importe en dolares, con los decimales que su tamano pide. */
export function useUsd(): (importe: string | number) => string {
  const { locale } = useLocale();
  return (importe) => {
    const valor = Number(importe);
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: decimales(valor),
    }).format(valor);
  };
}

/** Un porcentaje sin decimales, o con uno cuando es menor que 10. */
export function usePercent(): (fraccion: number) => string {
  const { locale } = useLocale();
  return (fraccion) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      maximumFractionDigits: fraccion < 0.1 && fraccion > 0 ? 1 : 0,
    }).format(fraccion);
}

/** Un dia `YYYY-MM-DD` (UTC) con el dia y el mes corto. */
export function useShortDay(): (dia: string) => string {
  const { locale } = useLocale();
  const formato = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
  return (dia) => formato.format(new Date(`${dia}T00:00:00Z`));
}

/** Un instante con dia, mes corto y hora, en la hora de quien mira. */
export function useMoment(): (instante: string) => string {
  const { locale } = useLocale();
  const formato = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
  return (instante) => formato.format(new Date(instante));
}

/** Un dia `YYYY-MM-DD` con el dia, el mes en letras y el ano. */
export function useLongDay(): (dia: string) => string {
  const { locale } = useLocale();
  const formato = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  return (dia) => formato.format(new Date(`${dia}T00:00:00Z`));
}

/** Cuanto se dice de un importe: la cifra y, debajo, lo que la aclara. */
export interface AmountView {
  readonly main: string;
  readonly note: string | null;
}

/**
 * Un importe, o los tokens cuando no hay precio publicado (2026-10-11).
 *
 * "Sin precio" no es "sin dato". Lo que no tiene precio **nunca** se escribe como
 * cero: sale en tokens si el proveedor los conto; si no los reporta --el servicio de
 * vectores de Google no lo hace--, en cuantas consultas fueron; y solo cuando no hay
 * ni eso, como "Sin precio". "Plan gratuito" se dice solo si el servidor lo respalda.
 */
export function useAmount(): (total: SpendTotal, unpriced?: UnpricedUsage) => AmountView {
  const { locale, t } = useLocale();
  const usd = useUsd();
  const cuenta = new Intl.NumberFormat(locale);
  return (total, unpriced) => {
    const tokens = unpriced?.tokens ?? 0;
    // Las llamadas sin precio que tampoco traen tokens: el servicio de vectores de
    // Google no los reporta. De esas se dice cuantas fueron, que es lo que se sabe.
    const sinRecuento = unpriced?.uncounted ?? 0;
    const consultas =
      sinRecuento === 1
        ? t("spend_panel.tokens.lookup_one")
        : t("spend_panel.tokens.lookups", { count: cuenta.format(sinRecuento) });
    const gratis = unpriced?.free_plan === true ? t("spend_panel.tokens.free_plan") : null;
    const medido = Number(total.measured_usd);
    if (medido === 0 && total.unmeasured_count > 0) {
      if (tokens > 0) {
        return {
          main: t("spend_panel.tokens.count", { amount: cuenta.format(tokens) }),
          note: gratis,
        };
      }
      return sinRecuento > 0
        ? { main: consultas, note: gratis }
        : { main: t("spend_panel.not_measured"), note: null };
    }
    if (tokens === 0 && sinRecuento === 0) {
      return { main: usd(medido), note: null };
    }
    const tambien =
      tokens > 0
        ? t("spend_panel.tokens.also", { amount: cuenta.format(tokens) })
        : t("spend_panel.tokens.also_lookups", { lookups: consultas });
    return { main: usd(medido), note: gratis === null ? tambien : `${tambien} · ${gratis}` };
  };
}
