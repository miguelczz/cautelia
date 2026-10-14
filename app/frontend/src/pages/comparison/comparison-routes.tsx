// La comparacion dentro del enrutador: `/compare`.
//
// La ruta resuelve lo que la pantalla no debe saber buscar: las tres
// aseguradoras, que salen del directorio del sitio. Mientras no llega, un
// esqueleto; si falla, el aviso con su reintento.

import { useQuery } from "@tanstack/react-query";

import { toProblemView } from "../../shared/api-client/problems";
import { siteQueryOptions } from "../../shared/api-client/site";
import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { PageSkeleton } from "../../shared/ui/page-skeletons";
import { ComparisonPage } from "./comparison-page";
import { askInsurer, exampleIssuerName } from "./comparison-port";

export function ComparisonRoutePage() {
  const { t, locale } = useLocale();
  const consulta = useQuery(siteQueryOptions());

  if (consulta.isPending) {
    return <PageSkeleton kind="compare" label={t("comparison.page.loading")} />;
  }
  if (consulta.isError) {
    return (
      <div className="mx-auto max-w-content px-4 py-12">
        <InlineAlert
          tone="danger"
          action={
            <Button
              variant="secondary"
              onClick={() => {
                void consulta.refetch();
              }}
            >
              {t("action.retry")}
            </Button>
          }
        >
          <p>{toProblemView(consulta.error).message(t)}</p>
        </InlineAlert>
      </div>
    );
  }

  return (
    <ComparisonPage
      insurers={consulta.data.tenants.map((aseguradora) => ({
        tenantId: aseguradora.tenant_id,
        displayName: aseguradora.display_name,
        kind: aseguradora.kind,
        examplePolicy: aseguradora.example_policy,
        issuedBy: exampleIssuerName(aseguradora),
        brand: aseguradora.brand ?? null,
      }))}
      // El idioma de la pantalla lo pone la ruta y no la pantalla: es el respaldo
      // que impide que la misma pregunta vuelva contestada en dos idiomas cuando el
      // texto no trae senal suficiente (BR2.1).
      ask={(tenantId, question) => askInsurer(tenantId, question, { locale })}
    />
  );
}
