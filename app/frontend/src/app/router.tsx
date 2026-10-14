// Las rutas de la interfaz (TanStack Router, ADR-002).
//
// U6 declaro tres --el inicio, las paginas de estado y "no encontrada"-- y U13
// anade las dos suyas: el chat de una aseguradora y el resumen de traza de una
// de sus respuestas. Cada unidad con pantallas agrega las suyas aqui **y** en
// el registro del arnes (`e2e/visitable-routes.ts`): la comprobacion de
// completitud compara los dos y falla nombrando la ruta que falte (BR7.1).

import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
  type RouterHistory,
} from "@tanstack/react-router";

import { CasesRoutePage, ExampleCaseRoutePage } from "../pages/cases/cases-routes";
import { ChatRoutePage } from "../pages/chat/chat-routes";
import { ComparisonRoutePage } from "../pages/comparison/comparison-routes";
import { PoliciesRoutePage } from "../pages/policies/policies-routes";
import { GuideRoutePage } from "../pages/guide/guide-routes";
import { HomePage } from "../pages/home/home-page";
import {
  CaseLinkRedeemRoutePage,
  InboxCaseRoutePage,
  InboxQueueRoutePage,
  VisitorCaseRoutePage,
} from "../pages/inbox/inbox-routes";
import { NotFoundPage, StatusRoutePage } from "../pages/status/status-routes";
import { TelemetryRoutePage } from "../pages/telemetry/telemetry-routes";
import { TraceRoutePage } from "../pages/trace/trace-routes";
import { VoiceRoutePage } from "../pages/voice/voice-routes";
import { AppShell } from "./shell/app-shell";

const rootRoute = createRootRoute({
  component: AppShell,
  notFoundComponent: NotFoundPage,
});

// La raiz de cautelia.app es la landing, que sirve Cloudflare Pages antes de
// llegar aqui (decision de Miguel, 2026-10-06). El inicio del aplicativo vive en
// /home; la raiz solo se alcanza por el dominio directo de Cloud Run y redirige.
const rootRedirectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    // TanStack Router senala una redireccion lanzandola: es su contrato, no un
    // error, y la regla del linter no lo distingue.
    // eslint-disable-next-line @typescript-eslint/only-throw-error
    throw redirect({ to: "/home" });
  },
});

// `onePage`: el inicio cabe en una sola vista en un computador con espacio
// (decision de Miguel, 2026-10-06); en telefono y tablet se desplaza como siempre.
const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/home",
  component: HomePage,
  staticData: { onePage: true },
});

// La guia "Como funciona" (decision de Miguel, 2026-10-06): el paso a paso y el
// instructivo, a donde lleva el boton bajo las aseguradoras del inicio. Cabe en una
// sola vista en un computador con espacio, como el inicio.
const guideRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/how-it-works",
  component: GuideRoutePage,
  staticData: { onePage: true },
});

const statusRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/status/$kind",
  component: StatusRoutePage,
});

// La telemetria (2026-10-09): el gasto y los resultados, en dos pestanas de una
// sola pagina. La pestana va en la direccion.
const telemetryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/telemetry",
  component: TelemetryRoutePage,
  validateSearch: (search: Record<string, unknown>): { view?: "quality" } =>
    search.view === "quality" ? { view: "quality" } : {},
});

// Las direcciones de antes llevan a su pestana: la landing y los enlaces viejos
// apuntan a `/metrics`.
const metricsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/metrics",
  beforeLoad: () => {
    // eslint-disable-next-line @typescript-eslint/only-throw-error -- el contrato de TanStack Router
    throw redirect({ to: "/telemetry", search: { view: "quality" } });
  },
});

// La pestana de polizas (fase 2, 2026-10-08): las polizas de ejemplo de cada
// aseguradora y que preguntar. Publica y siempre en la barra, como la guia. `onePage`:
// en un computador con espacio la lista y el detalle llenan la vista y el detalle se
// desplaza por dentro (2026-10-09). `tenant`: la aseguradora que se abre, desde el
// boton "Ver polizas" del inicio.
const policiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/policies",
  component: PoliciesRoutePage,
  staticData: { onePage: true },
  validateSearch: (search: Record<string, unknown>): { tenant?: string } =>
    typeof search.tenant === "string" && search.tenant.trim() !== ""
      ? { tenant: search.tenant }
      : {},
});

// La pagina de casos (2026-10-11): el caso propio de quien visita y los casos de ejemplo
// de cada aseguradora. Publica y siempre en la barra, donde antes estaba "Polizas".
// `tenant`: la aseguradora cuyos casos de ejemplo se abren, desde el enlace de vuelta
// de un caso.
const casesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/cases",
  component: CasesRoutePage,
  validateSearch: (search: Record<string, unknown>): { tenant?: string } =>
    typeof search.tenant === "string" && search.tenant.trim() !== ""
      ? { tenant: search.tenant }
      : {},
});

// Un caso de ejemplo, solo lectura. El servidor responde igual ante un caso que no es de
// ejemplo que ante uno que no existe.
const exampleCaseRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/cases/$tenantId/$caseId",
  component: ExampleCaseRoutePage,
});

const spendRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/spend",
  beforeLoad: () => {
    // eslint-disable-next-line @typescript-eslint/only-throw-error -- el contrato de TanStack Router
    throw redirect({ to: "/telemetry", search: {} });
  },
});

// La comparacion entre aseguradoras (U23). La direccion es la que el inicio ya
// enlaza para la superficie `comparison`.
const comparisonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/compare",
  component: ComparisonRoutePage,
});

// `fill` en `staticData`: el chat **llena la vista** y no crece con cada turno
// (decision de Miguel, 2026-10-06); lo que se desplaza es la conversacion, dentro
// de su ventana, nunca la pagina. Lo declara la ruta y lo lee el marco.
const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/t/$tenantId/chat",
  component: ChatRoutePage,
  staticData: { fill: true },
  // `ask`: el mensaje que se envia solo al abrir, desde la pestana de polizas.
  validateSearch: (search: Record<string, unknown>): { ask?: string } =>
    typeof search.ask === "string" && search.ask.trim() !== "" ? { ask: search.ask } : {},
});

// La consola de llamada (U16). Va junto al chat y no bajo el: son dos canales
// hermanos de la misma aseguradora, no uno dentro del otro. `onePage`: con la llamada
// en curso, en escritorio la llamada y la transcripcion llenan la vista y la
// transcripcion se desplaza por dentro (2026-10-09).
const voiceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/t/$tenantId/call",
  component: VoiceRoutePage,
  staticData: { onePage: true },
});

const traceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/t/$tenantId/trace/$traceId",
  component: TraceRoutePage,
});

// --- Las cuatro de la bandeja (U14) -------------------------------------------
//
// El idioma elegido se recuerda en todas las pantallas (decision de Miguel,
// 2026-10-06, que reemplaza BR1.6): ya no es cosa de la bandeja.
const inboxQueueRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/t/$tenantId/inbox",
  component: InboxQueueRoutePage,
  // Los cuatro filtros viven en la direccion y **solo esos cuatro**: lo que no
  // reconoce no viaja, asi que una direccion con cualquier otra cosa no la arrastra
  // hasta la consulta.
  validateSearch: (busqueda: Record<string, unknown>) => {
    const leer = (clave: string): string | undefined => {
      const valor = busqueda[clave];
      return typeof valor === "string" && valor !== "" ? valor : undefined;
    };
    return {
      ...(leer("state") === undefined ? {} : { state: leer("state") }),
      ...(leer("channel") === undefined ? {} : { channel: leer("channel") }),
      ...(leer("language") === undefined ? {} : { language: leer("language") }),
      ...(leer("priority") === undefined ? {} : { priority: leer("priority") }),
    };
  },
});

const inboxCaseRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/t/$tenantId/inbox/$caseId",
  component: InboxCaseRoutePage,
});

// El canje del enlace. El token viaja en el **fragmento** (`/c#<token>`), que el
// enrutador no ve y el navegador nunca manda al servidor ni en `Referer` (BR5.6).
const caseLinkRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/c",
  component: CaseLinkRedeemRoutePage,
});

const visitorCaseRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/c/$tenantId/$caseId",
  component: VisitorCaseRoutePage,
});

export const routeTree = rootRoute.addChildren([
  rootRedirectRoute,
  homeRoute,
  guideRoute,
  statusRoute,
  telemetryRoute,
  metricsRoute,
  policiesRoute,
  casesRoute,
  exampleCaseRoute,
  spendRoute,
  comparisonRoute,
  chatRoute,
  voiceRoute,
  traceRoute,
  inboxQueueRoute,
  inboxCaseRoute,
  caseLinkRoute,
  visitorCaseRoute,
]);

export function createAppRouter(history?: RouterHistory) {
  return createRouter({
    routeTree,
    ...(history === undefined ? {} : { history }),
    // Sin precarga al pasar el puntero: cada ruta pide sus datos al abrirse.
    defaultPreload: false,
  });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }

  /** Lo que una ruta declara de como se asienta en la ventana (ver `Frame`). */
  interface StaticDataRouteOption {
    readonly fill?: boolean;
    readonly onePage?: boolean;
  }
}
