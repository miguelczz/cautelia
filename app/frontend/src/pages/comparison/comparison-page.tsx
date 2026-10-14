// La vista de comparacion (U23, US2.9): la misma pregunta de cobertura respondida
// por las tres aseguradoras lado a lado.
//
// Tres cosas que no puede romper:
// - el aviso de demostracion va **antes** del campo de pregunta, y quien responde
//   se dice en cada columna desde antes de preguntar: las columnas no repiten la
//   apertura de cada aseguradora (Q1, A);
// - cada columna tiene su estado y su fallo (BR2.2): una que responde no espera a
//   las otras, y una que falla no borra las otras;
// - la vista no redacta la diferencia entre columnas (BR3.2): se lee en las
//   clausulas citadas.
//
// Lo preguntado y lo respondido se recuerda en el navegador por 24 horas
// (`comparison-storage.ts`). Todo texto sale del catalogo. Mandar la pregunta es un
// puerto (`ask`): esta pantalla no sabe por donde viaja.

import { ArrowCounterClockwiseIcon, PaperPlaneRightIcon } from "@phosphor-icons/react";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { tenantSurfaceHref } from "../../app/surfaces";
import type { Locale } from "../../shared/copy/copy-keys";
import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { LONG_PAGE_CONTENT, PAGE_TITLE } from "../../shared/ui/page-layout";
import { Textarea } from "../../shared/ui/textarea";
import { Column } from "./comparison-column";
import { askedAtLabel, exampleQuestions } from "./comparison-labels";
import {
  anyLoading,
  disclosureComplete,
  idleColumns,
  restoreColumns,
  settleColumn,
  startColumns,
  startQuestion,
  type AskInsurer,
  type ColumnOutcome,
  type ComparisonColumn,
  type ComparisonInsurer,
} from "./comparison-state";
import {
  clearComparison,
  inFlight,
  loadComparison,
  saveComparison,
  trackInFlight,
  updateComparison,
} from "./comparison-storage";

export interface ComparisonPageProps {
  readonly insurers: readonly ComparisonInsurer[];
  readonly ask: AskInsurer;
}

/** La pregunta que esta en pantalla: la que se acaba de hacer o la que se recupero. */
interface Asked {
  readonly askedAt: number;
  readonly locale: Locale;
  readonly question: string;
}

interface Recovered {
  readonly asked: Asked;
  readonly columns: readonly ComparisonColumn[];
}

/** Lo que el navegador recordaba, listo para pintar, o `null` si no habia nada vigente. */
function recover(insurers: readonly ComparisonInsurer[]): Recovered | null {
  const guardada = loadComparison(
    Date.now(),
    insurers.map((aseguradora) => aseguradora.tenantId),
  );
  if (guardada === null) {
    return null;
  }
  return {
    asked: { askedAt: guardada.askedAt, locale: guardada.locale, question: guardada.question },
    columns: restoreColumns(
      guardada.columns,
      (tenantId) => inFlight(guardada.askedAt, tenantId) !== undefined,
    ),
  };
}

export function ComparisonPage({ insurers, ask }: ComparisonPageProps) {
  const { t, locale } = useLocale();
  const [recuperada] = useState(() => recover(insurers));
  const [columnas, setColumnas] = useState<readonly ComparisonColumn[]>(
    () => recuperada?.columns ?? idleColumns(insurers),
  );
  const [preguntada, setPreguntada] = useState<Asked | null>(recuperada?.asked ?? null);
  const [borrador, setBorrador] = useState("");
  const [fueraDePropos, setFueraDePropos] = useState(false);
  //: Si la demostracion no acepta casos nuevos ahora mismo (BR3.2 de U20). Es
  //: estado de la vista y no de una columna: el motivo es el mismo para las tres.
  const [demoCerrada, setDemoCerrada] = useState(false);
  const [ahora] = useState(() => Date.now());
  // Despues de mandar o de empezar otra pregunta, el foco no se pierde con el boton
  // que desaparece: va a la tarjeta de la pregunta o al cuadro de texto.
  const enfocarPregunta = useRef(false);
  const enfocarCuadro = useRef(false);
  const idAviso = useId();
  const idEjemplos = useId();
  const idPregunta = useId();

  const completa = disclosureComplete(insurers);
  const cargando = anyLoading(columnas);

  /**
   * Cierra **una** columna con lo que llego. No hace falta comprobar de que consulta
   * viene: "Nueva pregunta" y el cuadro de texto esperan a que ninguna columna cargue.
   */
  const mostrar = useCallback((tenantId: string, resultado: ColumnOutcome) => {
    // **Quien decide que una pregunta es fuera de proposito es el servidor** (Q3),
    // asi que llega como resultado y no como una heuristica de este lado. Es el
    // mismo para las tres --el mismo texto, el mismo idioma, el mismo reconocedor--,
    // por eso se dice una vez y la pregunta se borra: no hubo nada que comparar.
    if (resultado.kind === "out_of_scope") {
      setFueraDePropos(true);
      setPreguntada(null);
    }
    // La demostracion estrechada (BR3.2 de U20) es como la de arriba --no hubo nada
    // que comparar-- y tambien es la misma para las tres. Lo que **no** lleva es el
    // enlace al chat: alli pasa lo mismo.
    if (resultado.kind === "demo_closed") {
      setDemoCerrada(true);
      setPreguntada(null);
    }
    setColumnas((previas) => settleColumn(previas, tenantId, resultado));
  }, []);

  // Si la persona salio y volvio sin recargar, lo que seguia en vuelo se engancha
  // otra vez: la respuesta puede llegar ahora.
  useEffect(() => {
    if (recuperada === null) {
      return;
    }
    for (const columna of recuperada.columns) {
      const pendiente =
        columna.state === "loading"
          ? inFlight(recuperada.asked.askedAt, columna.tenantId)
          : undefined;
      if (pendiente !== undefined) {
        void pendiente.then((resultado) => {
          mostrar(columna.tenantId, resultado);
        });
      }
    }
  }, [recuperada, mostrar]);

  /** Tres llamadas independientes: cada una cierra **su** columna cuando llega. */
  function consultar(
    destinos: readonly ComparisonInsurer[],
    consulta: number,
    pregunta: string,
  ): void {
    // Esperarlas juntas volveria la vista tan lenta como la mas lenta (BR2.2).
    for (const aseguradora of destinos) {
      const resultado = ask(aseguradora.tenantId, pregunta).catch((): ColumnOutcome => ({
        kind: "failed",
      }));
      // Se guarda este de la pagina montada o no; la columna lo muestra aparte.
      trackInFlight(consulta, aseguradora.tenantId, resultado);
      void resultado.then((salida) => {
        mostrar(aseguradora.tenantId, salida);
      });
    }
  }

  function enviar(): void {
    const pregunta = borrador.trim();
    if (pregunta === "" || cargando) {
      return;
    }
    const consulta = Date.now();
    const empezadas = startQuestion(columnas);
    enfocarPregunta.current = true;
    setFueraDePropos(false);
    setDemoCerrada(false);
    setPreguntada({ askedAt: consulta, locale, question: pregunta });
    setBorrador("");
    setColumnas(empezadas);
    saveComparison({ askedAt: consulta, locale, question: pregunta, columns: empezadas });
    consultar(insurers, consulta, pregunta);
  }

  function volverAPreguntar(aseguradora: ComparisonInsurer): void {
    if (preguntada === null) {
      return;
    }
    const solo = [aseguradora.tenantId];
    setColumnas((previas) => startColumns(previas, solo));
    updateComparison(preguntada.askedAt, (guardadas) => startColumns(guardadas, solo));
    consultar([aseguradora], preguntada.askedAt, preguntada.question);
  }

  function empezarOtra(): void {
    enfocarCuadro.current = true;
    clearComparison();
    setPreguntada(null);
    setColumnas(idleColumns(insurers));
    setFueraDePropos(false);
    setDemoCerrada(false);
  }

  return (
    <div className={LONG_PAGE_CONTENT} data-testid="comparison-page">
      <header className="flex max-w-[46rem] flex-col gap-3">
        <h1 className={PAGE_TITLE}>{t("comparison.page.title")}</h1>
        <p className="text-lead text-fg-secondary">{t("comparison.page.lead")}</p>
      </header>

      {demoCerrada ? (
        <InlineAlert tone="info" data-testid="comparison-demo-closed" role="status">
          <p>{t("demo.reset.surfaces_closed")}</p>
        </InlineAlert>
      ) : null}

      {fueraDePropos ? (
        <InlineAlert tone="info" data-testid="comparison-out-of-scope" role="status">
          <div className="flex flex-col gap-2">
            <p>{t("comparison.out_of_scope.explanation")}</p>
            <ul className="flex flex-col gap-1 tablet:flex-row tablet:flex-wrap tablet:gap-3">
              {insurers.map((aseguradora) => (
                <li key={aseguradora.tenantId}>
                  <a
                    href={tenantSurfaceHref("chat", aseguradora.tenantId)}
                    className="inline-flex min-h-11 items-center text-link underline underline-offset-4"
                  >
                    {t("comparison.out_of_scope.chat_link", {
                      insurer: aseguradora.displayName,
                    })}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </InlineAlert>
      ) : null}

      {preguntada !== null ? (
        <section
          aria-labelledby={idPregunta}
          data-testid="comparison-asked"
          ref={(nodo) => {
            if (nodo !== null && enfocarPregunta.current) {
              enfocarPregunta.current = false;
              nodo.focus();
            }
          }}
          tabIndex={-1}
          className="flex flex-col gap-4 rounded-surface border border-hairline bg-surface p-4 tablet:flex-row tablet:items-start tablet:justify-between tablet:p-6"
        >
          <div className="flex min-w-0 flex-col gap-1.5">
            <p id={idPregunta} className="text-caption text-fg-secondary">
              {t("comparison.asked.label")}
            </p>
            <p lang={preguntada.locale} className="font-display text-lead break-words text-fg">
              {preguntada.question}
            </p>
            <p className="text-caption text-fg-secondary">
              {t("comparison.asked.meta", {
                when: askedAtLabel(preguntada.askedAt, ahora, locale),
              })}
            </p>
          </div>
          <Button
            variant="secondary"
            className="self-start"
            disabled={cargando}
            onClick={empezarOtra}
          >
            <ArrowCounterClockwiseIcon aria-hidden="true" focusable="false" size={18} />
            {t("comparison.asked.new")}
          </Button>
        </section>
      ) : null}

      {preguntada === null && completa ? (
        <form
          data-testid="comparison-composer"
          className="flex flex-col gap-4 rounded-surface border border-hairline bg-surface p-4 tablet:p-6"
          onSubmit={(evento) => {
            evento.preventDefault();
            enviar();
          }}
        >
          <div className="flex flex-col gap-1">
            <label htmlFor="comparison-composer" className="font-medium text-fg">
              {t("comparison.composer.label")}
            </label>
            {/* Antes del campo: quien escribe ya leyo que es una demostracion y que lo
                que envie cuenta contra los limites. */}
            <p
              id={idAviso}
              data-testid="comparison-notice"
              className="text-caption text-fg-secondary"
            >
              {t("comparison.disclosure.demo")}
            </p>
          </div>
          <Textarea
            id="comparison-composer"
            rows={3}
            value={borrador}
            aria-describedby={idAviso}
            ref={(nodo) => {
              if (nodo !== null && enfocarCuadro.current) {
                enfocarCuadro.current = false;
                nodo.focus();
              }
            }}
            onChange={(evento) => {
              setBorrador(evento.target.value);
            }}
          />
          <div className="flex flex-col gap-2" role="group" aria-labelledby={idEjemplos}>
            <p id={idEjemplos} className="text-caption text-fg-secondary">
              {t("comparison.examples.title")}
            </p>
            <ul className="flex flex-wrap gap-2">
              {exampleQuestions().map((ejemplo, indice) => (
                <li key={indice}>
                  <Button
                    variant="secondary"
                    size="compact"
                    className="h-auto py-2 text-left font-normal whitespace-normal"
                    onClick={() => {
                      setBorrador(ejemplo(t));
                    }}
                  >
                    {ejemplo(t)}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <Button type="submit" variant="primary" disabled={borrador.trim() === ""}>
              <PaperPlaneRightIcon aria-hidden="true" focusable="false" size={20} weight="fill" />
              {t("comparison.composer.send")}
            </Button>
          </div>
        </form>
      ) : null}

      {completa ? null : (
        <InlineAlert tone="warning" data-testid="comparison-incomplete" role="status">
          <p>{t("comparison.disclosure.incomplete")}</p>
        </InlineAlert>
      )}

      <div className="grid gap-4 desktop:grid-cols-3" data-testid="comparison-columns">
        {columnas.map((columna) => {
          const aseguradora = insurers.find((a) => a.tenantId === columna.tenantId);
          return aseguradora === undefined ? null : (
            <Column
              key={columna.tenantId}
              insurer={aseguradora}
              column={columna}
              onAskAgain={() => {
                volverAPreguntar(aseguradora);
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
