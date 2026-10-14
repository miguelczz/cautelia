// La ruta del tablero de gasto, por el cliente generado (U22, 2026-10-09).
//
// Es publica y sin credencial. La marca de "tu caso" la decide el servidor con la
// cookie del navegador, que esta capa no lee ni escribe.

import type {
  ActivitySpend,
  BudgetState,
  BudgetStatus,
  CaseSpendItem,
  ComparisonPart,
  ComparisonSpendItem,
  CountedSpend,
  DaySpend,
  Money,
  ProviderName,
  ProviderSpend,
  SpendActivity,
  SpendPanel,
  SpendTotal,
  UnpricedUsage,
} from "../api";
import { getSpendOptions } from "../api/@tanstack/react-query.gen";

export type {
  ActivitySpend,
  BudgetState,
  BudgetStatus,
  CaseSpendItem,
  ComparisonPart,
  ComparisonSpendItem,
  CountedSpend,
  DaySpend,
  Money,
  ProviderName,
  ProviderSpend,
  SpendActivity,
  SpendPanel,
  SpendTotal,
  UnpricedUsage,
};

/** La consulta de `GET /api/spend`: el tablero entero. Solo lectura. */
export function spendQueryOptions() {
  return getSpendOptions();
}
