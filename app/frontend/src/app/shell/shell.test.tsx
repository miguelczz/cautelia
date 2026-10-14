import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { LOCALE_STORAGE_KEY, SHARED_LOCALE_KEY } from "../../shared/i18n/initial-locale";
import { createTranslate } from "../../shared/i18n/translate";
import { AUTHOR } from "../../shared/site/author";
import { LANDING_URL } from "../../shared/site/landing";
import { THEME_STORAGE_KEY } from "../../shared/theme/preference";
import { renderWithProviders } from "../testing";
import { Frame } from "./frame";
import { LandingLink } from "./landing-link";
import { LanguageSelector } from "./language-selector";
import { SiteFooter } from "./site-footer";
import { SurfaceNav } from "./surface-nav";
import { ThemeToggle } from "./theme-toggle";

// BR2.5, BR1.3, BR4.1, BR4.4, BR7.4: los selectores, la navegacion de lo
// montado, el pie y el enlace para saltar al contenido.

const es = createTranslate("es");
const en = createTranslate("en");

describe("el selector de idioma", () => {
  it("muestra los nombres completos, cada uno en su lengua", () => {
    renderWithProviders(<LanguageSelector />, "es");
    const grupo = screen.getByRole("group", { name: es("shell.language.group") });

    expect(within(grupo).getByRole("button", { name: "Español" }).getAttribute("lang")).toBe("es");
    expect(within(grupo).getByRole("button", { name: "English" }).getAttribute("lang")).toBe("en");
    expect(
      within(grupo).getByRole("button", { name: "Español" }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("cambia el idioma del documento, lo anuncia una vez en el idioma nuevo y deja el foco", async () => {
    renderWithProviders(<LanguageSelector />, "es");
    const ingles = screen.getByRole("button", { name: "English" });

    await userEvent.click(ingles);

    expect(document.documentElement.lang).toBe("en");
    expect(screen.getByTestId("announcer-status").textContent).toBe(en("shell.language.changed"));
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "English" }));
    expect(screen.getByRole("group", { name: en("shell.language.group") })).toBeDefined();
    // La eleccion se recuerda, y se deja tambien para la landing.
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en");
    expect(window.localStorage.getItem(SHARED_LOCALE_KEY)).toBe("en");
  });
});

describe("el selector de modo", () => {
  it("cambia todo el documento de inmediato, lo guarda y deja el foco en el boton", async () => {
    renderWithProviders(<ThemeToggle />, "es");
    const claro = screen.getByRole("button", { name: es("shell.theme.light") });
    // Sin eleccion guardada el aplicativo abre en oscuro, el modo de la landing.
    expect(
      screen.getByRole("button", { name: es("shell.theme.dark") }).getAttribute("aria-pressed"),
    ).toBe("true");

    await userEvent.click(claro);

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(claro.getAttribute("aria-pressed")).toBe("true");
    expect(document.activeElement).toBe(claro);
  });

  it("muestra solo los iconos y deja el nombre del catalogo en aria-label", () => {
    renderWithProviders(<ThemeToggle />, "es");

    for (const clave of ["shell.theme.light", "shell.theme.dark"] as const) {
      const boton = screen.getByRole("button", { name: es(clave) });
      expect(boton.getAttribute("aria-label")).toBe(es(clave));
      expect(boton.textContent).toBe("");
      expect(boton.querySelector("svg")).not.toBeNull();
    }
  });
});

describe("los selectores de la barra, sin caja", () => {
  it("el idioma elegido lleva la linea de cobre y no un fondo; el resto de la letra es la tinta fuerte", () => {
    renderWithProviders(<LanguageSelector />, "es");
    const grupo = screen.getByTestId("language-selector");
    const elegido = within(grupo).getByRole("button", { pressed: true });
    const otro = within(grupo).getByRole("button", { pressed: false });

    expect(elegido.className).not.toContain("bg-selected");
    expect(elegido.className).toContain("text-fg");
    expect(elegido.querySelector("[aria-hidden]")?.className).toContain("bg-copper");
    expect(elegido.querySelector("[aria-hidden]")?.className).toContain("scale-x-100");
    expect(otro.querySelector("[aria-hidden]")?.className).toContain("scale-x-0");
  });

  it("el icono del modo activo va en el color de la marca, sin fondo; el otro en la tinta", () => {
    renderWithProviders(<ThemeToggle />, "es");
    const grupo = screen.getByTestId("theme-toggle");
    const activo = within(grupo).getByRole("button", { pressed: true });
    const inactivo = within(grupo).getByRole("button", { pressed: false });

    expect(activo.className).toContain("text-brand");
    expect(activo.className).not.toContain("bg-selected");
    expect(inactivo.className).toContain("text-fg");
    expect(inactivo.className).not.toContain("text-brand");
  });
});

describe("el marco", () => {
  it("el primer elemento que recibe el foco es saltar al contenido, y lleva al contenido", async () => {
    renderWithProviders(
      <Frame brand={<a href="/">Cautelia</a>}>
        <p>contenido</p>
      </Frame>,
    );

    await userEvent.tab();

    const salto = screen.getByRole("link", { name: es("shell.skip_to_content") });
    expect(document.activeElement).toBe(salto);
    fireEvent.click(salto);
    expect(document.activeElement).toBe(screen.getByRole("main"));
  });
});

describe("como el marco se asienta en la ventana", () => {
  function marco(props: { readonly fill?: boolean; readonly onePage?: boolean }) {
    renderWithProviders(
      <Frame brand={<a href="/">Cautelia</a>} {...props}>
        <p>contenido</p>
      </Frame>,
    );
    // `main` cuelga de la raiz del marco, que es la que se asienta en la ventana.
    const raiz = screen.getByRole("main").parentElement;
    if (raiz === null) {
      throw new Error("main has no parent");
    }
    return raiz;
  }

  it("por omision crece con su contenido", () => {
    const raiz = marco({});
    expect(raiz.className).toContain("min-h-dvh");
    expect(raiz.className).not.toContain("roomy:");
  });

  it("una sola pantalla mide la ventana solo en un computador con espacio", () => {
    const raiz = marco({ onePage: true });
    expect(raiz.className).toContain("min-h-dvh");
    expect(raiz.className).toContain("roomy:h-dvh");
    // Si no cabe, se desplaza dentro de `main` y no se recorta.
    expect(screen.getByRole("main").className).toContain("roomy:overflow-y-auto");
  });

  it("la que llena la vista la llena siempre", () => {
    expect(marco({ fill: true }).className).toContain("h-dvh");
  });
});

describe("la navegacion de superficies", () => {
  it("sin nada montado ni configurado quedan las aseguradoras y los casos", () => {
    // Aseguradoras y casos no dependen de ninguna superficie (fase 2 y 3, 2026-10-08; los
    // casos reemplazaron a las polizas en la barra el 2026-10-11).
    renderWithProviders(<SurfaceNav surfaces={["chat"]} links={{}} currentPath="/" />);
    const navegacion = screen.getByRole("navigation", { name: es("shell.nav_label") });
    expect(
      within(navegacion)
        .getAllByRole("link")
        .map((enlace) => enlace.textContent),
    ).toEqual([es("policies.nav_insurers"), es("cases.nav")]);
  });

  it("Casos queda marcado tambien dentro de un caso de ejemplo, y Polizas ya no esta en la barra", () => {
    renderWithProviders(
      <SurfaceNav surfaces={[]} links={{}} currentPath="/cases/una-aseguradora/un-caso" />,
    );
    const navegacion = screen.getByRole("navigation", { name: es("shell.nav_label") });

    expect(
      within(navegacion)
        .getByRole("link", { name: es("cases.nav") })
        .getAttribute("aria-current"),
    ).toBe("page");
    expect(within(navegacion).queryByRole("link", { name: /p[oó]lizas?/i })).toBeNull();
  });

  it("muestra solo los paneles montados y el enlace configurado, y marca el actual", () => {
    renderWithProviders(
      <SurfaceNav
        surfaces={["metrics_panel"]}
        links={{ readme_url: "https://example.org/readme" }}
        currentPath="/telemetry"
      />,
    );
    const navegacion = screen.getByRole("navigation", { name: es("shell.nav_label") });
    const enlaces = within(navegacion).getAllByRole("link");

    expect(enlaces.map((enlace) => enlace.textContent)).toEqual([
      es("policies.nav_insurers"),
      es("cases.nav"),
      es("surface.telemetry"),
      es("site.link.readme"),
    ]);
    expect(enlaces.map((enlace) => enlace.getAttribute("aria-current"))).toEqual([
      null,
      null,
      "page",
      null,
    ]);
  });

  it("los enlaces son texto en la fuente de titulos, en negrita, sin caja, con una linea de cobre que crece", () => {
    renderWithProviders(
      <>
        <SurfaceNav surfaces={["metrics_panel"]} links={{}} currentPath="/telemetry" />
        <ThemeToggle />
      </>,
    );
    const enlaces = within(screen.getByTestId("surface-nav")).getAllByRole("link");
    const selector = screen.getByTestId("theme-toggle");

    for (const enlace of enlaces) {
      expect(enlace.className).toContain("font-display");
      expect(enlace.className).toContain("font-semibold");
      expect(enlace.className).not.toContain("border");
      expect(enlace.className).toContain("min-h-11");
      // La linea de cobre: crece desde la izquierda y, en la pagina actual, esta entera.
      const linea = enlace.querySelector("[aria-hidden]");
      expect(linea?.className).toContain("bg-copper");
      expect(linea?.className).toContain("origin-left");
      const actual = enlace.getAttribute("aria-current") === "page";
      expect(linea?.className).toContain(actual ? "scale-x-100" : "scale-x-0");
      if (!actual) {
        expect(linea?.className).toContain("group-hover:scale-x-100");
        expect(linea?.className).toContain("group-focus-visible:scale-x-100");
      }
      // Sin movimiento reducido, la linea aparece de golpe.
      expect(linea?.className).toContain("motion-safe:transition-transform");
    }
    // Los selectores tambien sin caja, con las esquinas suaves del boton.
    expect(selector.className).not.toContain("border");
    expect(selector.querySelector("button")?.className).toContain("rounded-button");
  });

  it("mientras el directorio no llega ya pinta los enlaces, sin caja de espera", () => {
    renderWithProviders(<SurfaceNav surfaces={[]} links={{}} currentPath="/" pending />);

    expect(screen.getByRole("link", { name: es("surface.telemetry") })).toBeDefined();
    expect(document.querySelector("[aria-busy]")).toBeNull();
  });

  it("si el servidor dice que un panel no esta montado, su enlace se retira", () => {
    renderWithProviders(<SurfaceNav surfaces={[]} links={{}} currentPath="/" />);

    expect(screen.queryByRole("link", { name: es("surface.telemetry") })).toBeNull();
  });

  it("la navegacion no trae su propio menu: el menu del telefono es del marco", () => {
    renderWithProviders(<SurfaceNav surfaces={["metrics_panel"]} links={{}} currentPath="/" />);

    expect(screen.queryByRole("button", { name: /menu|menú/i })).toBeNull();
    expect(screen.getByRole("link", { name: es("surface.telemetry") })).toBeDefined();
  });
});

describe("el icono que vuelve a la landing", () => {
  it("es solo un icono, con su nombre accesible completo y su ayuda", () => {
    renderWithProviders(<LandingLink />);
    const enlace = screen.getByRole("link", { name: es("shell.nav.landing") });

    expect(enlace.getAttribute("href")).toBe(LANDING_URL);
    expect(enlace.getAttribute("title")).toBe(es("shell.nav.landing"));
    // Sin una sola palabra a la vista: lo que se ve es el icono.
    expect(enlace.textContent).toBe("");
    expect(enlace.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("es un icono de 44 x 44 sin caja, como el resto de la barra", () => {
    renderWithProviders(<LandingLink />);
    const enlace = screen.getByTestId("nav-landing");

    expect(enlace.className).toContain("rounded-button");
    expect(enlace.className).not.toContain("border");
    expect(enlace.className).toContain("min-w-11");
    expect(enlace.className).toContain("min-h-11");
    expect(enlace.className).not.toContain("px-5");
  });
});

describe("el orden de la barra", () => {
  function barra() {
    renderWithProviders(
      <Frame
        brand={<a href="/">Cautelia</a>}
        nav={<SurfaceNav surfaces={["metrics_panel"]} links={{}} currentPath="/" />}
        trailing={<LandingLink />}
      >
        <p>contenido</p>
      </Frame>,
    );
    const cabecera = screen.getByRole("banner");
    return within(cabecera)
      .getAllByRole("link")
      .map((enlace) => enlace.getAttribute("data-testid") ?? enlace.textContent);
  }

  it("el icono de la landing es el ultimo de la fila, despues de los selectores", () => {
    const enlaces = barra();
    expect(enlaces.at(-1)).toBe("nav-landing");
    // Y la navegacion va antes de los selectores, como el documento lo dice.
    const cabecera = screen.getByRole("banner");
    const orden = [
      screen.getByTestId("surface-nav"),
      screen.getByTestId("language-selector"),
      screen.getByTestId("theme-toggle"),
      screen.getByTestId("nav-landing"),
    ];
    orden.forEach((elemento, indice) => {
      expect(cabecera.contains(elemento)).toBe(true);
      const siguiente = orden[indice + 1];
      if (siguiente !== undefined) {
        // Cada uno va antes que el siguiente en el documento: el orden de Tab es el que se ve.
        expect(
          (elemento.compareDocumentPosition(siguiente) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0,
        ).toBe(true);
      }
    });
  });
});

describe("el menu del telefono", () => {
  function barra() {
    renderWithProviders(
      <>
        <button type="button">fuera</button>
        <Frame
          brand={<a href="/">Cautelia</a>}
          nav={<SurfaceNav surfaces={["metrics_panel"]} links={{}} currentPath="/telemetry" />}
          trailing={<LandingLink />}
        >
          <p>contenido</p>
        </Frame>
      </>,
    );
    const boton = screen.getByRole("button", { name: es("shell.menu.button") });
    const idPanel = boton.getAttribute("aria-controls") ?? "";
    const panel = document.getElementById(idPanel);
    if (panel === null) {
      throw new Error("aria-controls no apunta a ningun panel");
    }
    return { boton, panel };
  }

  it("empieza cerrado y controla el panel que contiene la navegacion, los selectores y la landing", () => {
    const { boton, panel } = barra();

    expect(boton.getAttribute("aria-expanded")).toBe("false");
    expect(panel.getAttribute("data-open")).toBe("false");
    // Cerrado en telefono; desde tableta ese contenedor no se dibuja y sus hijos son la barra.
    expect(panel.className).toContain("max-tablet:hidden");
    expect(panel.className).toContain("tablet:contents");
    expect(boton.className).toContain("tablet:hidden");

    const enlaces = within(panel).getAllByRole("link");
    expect(
      enlaces.map((enlace) => enlace.getAttribute("data-testid") ?? enlace.textContent),
    ).toEqual([
      es("policies.nav_insurers"),
      es("cases.nav"),
      es("surface.telemetry"),
      "nav-landing",
    ]);
    // La pagina actual sigue marcada dentro del menu.
    expect(
      within(panel)
        .getByRole("link", { name: es("surface.telemetry") })
        .getAttribute("aria-current"),
    ).toBe("page");
    expect(within(panel).getByTestId("language-selector")).toBeDefined();
    expect(within(panel).getByTestId("theme-toggle")).toBeDefined();
  });

  it("se abre con el boton, lleva el foco al primer enlace y oscurece lo de detras", async () => {
    const { boton, panel } = barra();

    await userEvent.click(boton);

    expect(boton.getAttribute("aria-expanded")).toBe("true");
    expect(panel.getAttribute("data-open")).toBe("true");
    expect(panel.className).toContain("max-tablet:flex");
    expect(document.activeElement).toBe(
      within(panel).getByRole("link", { name: es("policies.nav_insurers") }),
    );
    expect(screen.getByTestId("menu-scrim")).toBeDefined();
  });

  it("Escape lo cierra y devuelve el foco al boton", async () => {
    const { boton, panel } = barra();
    await userEvent.click(boton);

    await userEvent.keyboard("{Escape}");

    expect(boton.getAttribute("aria-expanded")).toBe("false");
    expect(panel.getAttribute("data-open")).toBe("false");
    expect(document.activeElement).toBe(boton);
    expect(screen.queryByTestId("menu-scrim")).toBeNull();
  });

  it("el mismo boton lo cierra, y tocar fuera tambien", async () => {
    const { boton } = barra();

    await userEvent.click(boton);
    await userEvent.click(boton);
    expect(boton.getAttribute("aria-expanded")).toBe("false");

    await userEvent.click(boton);
    await userEvent.click(screen.getByRole("button", { name: "fuera" }));
    expect(boton.getAttribute("aria-expanded")).toBe("false");
  });

  it("cambiar de idioma no lo cierra: se puede elegir idioma y modo de una vez", async () => {
    const { boton, panel } = barra();
    await userEvent.click(boton);

    await userEvent.click(within(panel).getByRole("button", { name: "English" }));

    expect(boton.getAttribute("aria-expanded")).toBe("true");
  });

  it("el boton mide al menos 44 x 44 y no deja la pagina desplazable detras", async () => {
    const { boton } = barra();
    expect(boton.className).toContain("min-h-11");
    expect(boton.className).toContain("min-w-11");

    await userEvent.click(boton);
    expect(document.documentElement.style.overflow).toBe("hidden");
    await userEvent.keyboard("{Escape}");
    expect(document.documentElement.style.overflow).toBe("");
  });
});

describe("el pie en las pantallas que llenan la vista", () => {
  function conPie(fill: boolean) {
    renderWithProviders(
      <Frame brand={<a href="/">Cautelia</a>} footer={<SiteFooter links={{}} />} fill={fill}>
        <p>contenido</p>
      </Frame>,
    );
  }

  it("no lleva pie en ningun tamano, para que el chat llegue al borde de abajo", () => {
    conPie(true);
    expect(screen.queryByTestId("site-footer")).toBeNull();
  });

  it("marca la vista para que la pagina no tenga barra propia", () => {
    conPie(true);
    expect(document.querySelector("[data-fill-view]")).not.toBeNull();
  });

  it("en las demas pantallas el pie esta siempre", () => {
    conPie(false);
    expect(screen.getByTestId("site-footer")).toBeDefined();
    expect(document.querySelector("[data-fill-view]")).toBeNull();
  });
});

describe("el pie", () => {
  it("sin enlaces configurados dice que es una demostracion y quien la hizo", () => {
    renderWithProviders(<SiteFooter links={{}} />);
    const pie = screen.getByTestId("site-footer");
    expect(pie.textContent).toContain(es("shell.footer.demo"));
    expect(pie.textContent).toContain(es("shell.footer.made_by", { name: AUTHOR.name }));
    // Los unicos enlaces son los dos perfiles del autor.
    expect(within(pie).getAllByRole("link")).toHaveLength(2);
  });

  it("el perfil de LinkedIn se abre en pestana nueva, sin pasar la pagina de origen", () => {
    renderWithProviders(<SiteFooter links={{}} />, "en");
    const enlace = screen.getByRole("link", {
      name: en("shell.footer.linkedin_label", { name: AUTHOR.name }),
    });

    expect(enlace.getAttribute("href")).toBe(AUTHOR.linkedinUrl);
    expect(enlace.getAttribute("data-profile")).toBe("linkedin");
    expect(enlace.getAttribute("target")).toBe("_blank");
    expect(enlace.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("el perfil de GitHub se abre en pestana nueva, sin pasar la pagina de origen", () => {
    renderWithProviders(<SiteFooter links={{}} />, "es");
    const enlace = screen.getByRole("link", {
      name: es("shell.footer.github_label", { name: AUTHOR.name }),
    });

    expect(enlace.getAttribute("href")).toBe(AUTHOR.githubUrl);
    expect(enlace.getAttribute("data-profile")).toBe("github");
    expect(enlace.getAttribute("target")).toBe("_blank");
    expect(enlace.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("el perfil de GitHub es el de la persona, no el del repositorio", () => {
    expect(AUTHOR.githubUrl).toBe("https://github.com/miguelczz");
    expect(new URL(AUTHOR.githubUrl).pathname.split("/").filter(Boolean)).toEqual(["miguelczz"]);
  });

  it("los perfiles son enlaces de texto, sin borde ni forma de boton", () => {
    renderWithProviders(<SiteFooter links={{}} />);
    const lista = within(screen.getByTestId("site-author")).getByRole("list");

    expect(lista.className).not.toMatch(/\b(border|rounded-pill|bg-)/);
    for (const enlace of within(lista).getAllByRole("link")) {
      expect(enlace.className).not.toMatch(/\b(border|rounded-pill|bg-surface)/);
      expect(enlace.className).toContain("min-h-11");
      expect(enlace.className).toContain("min-w-11");
    }
  });

  it("al pasar el puntero el icono sube y una linea crece bajo el nombre, sin movimiento si se pide reducirlo", () => {
    renderWithProviders(<SiteFooter links={{}} />);
    const enlace = screen.getByRole("link", {
      name: es("shell.footer.github_label", { name: AUTHOR.name }),
    });
    const icono = enlace.querySelector("svg");
    const nombre = enlace.querySelector("span");

    expect(enlace.className).toContain("group");
    expect(enlace.className).toContain("hover:text-fg");
    // El desplazamiento y el crecimiento solo con movimiento permitido.
    expect(icono?.getAttribute("class")).toContain("motion-safe:group-hover:-translate-y-0.5");
    expect(nombre?.className).toContain("group-hover:bg-[length:100%_1px]");
    expect(nombre?.className).toContain("motion-safe:transition-[background-size]");
    // La transicion de tamano nunca corre sola: sin `motion-safe:`, la linea aparece de golpe.
    expect(nombre?.className).not.toMatch(/(^|\s)transition-/);
  });

  it("no pinta un fondo propio: hereda el de la pagina", () => {
    renderWithProviders(<SiteFooter links={{}} />);
    expect(screen.getByTestId("site-footer").className).not.toMatch(/\bbg-/);
  });

  it("con enlaces configurados los muestra primero, y despues el credito", () => {
    renderWithProviders(<SiteFooter links={{ video_url: "https://example.org/video" }} />, "en");
    const enlaces = within(screen.getByTestId("site-footer")).getAllByRole("link");
    expect(enlaces.map((enlace) => enlace.getAttribute("href"))).toEqual([
      "https://example.org/video",
      AUTHOR.linkedinUrl,
      AUTHOR.githubUrl,
    ]);
    expect(enlaces[0]?.textContent).toBe(en("site.link.video"));
  });
});
