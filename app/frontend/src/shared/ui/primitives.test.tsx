import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "../i18n/locale-provider";
import { createTranslate } from "../i18n/translate";
import { Button } from "./button";
import { DemoNotice } from "./demo-notice";
import { Disclosure, DisclosureContent, DisclosureTrigger } from "./disclosure";
import { InlineAlert } from "./inline-alert";
import { Input } from "./input";
import { Monogram } from "./monogram";
import { SegmentedToggle } from "./segmented-toggle";
import { Select } from "./select";
import { Skeleton } from "./skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";
import { Tag } from "./tag";
import { Textarea } from "./textarea";

// BR7.3, BR7.6, BR7.7 y los siete estados de las primitivas: por defecto,
// encima, foco, activo, deshabilitado, cargando y error. Lo que se prueba es lo
// que ve un lector y lo que permite el teclado; el aspecto lo mide el arnes.

describe("el boton", () => {
  it("cargando queda ocupado y no admite un segundo clic", async () => {
    const alPulsar = vi.fn();
    render(
      <Button loading onClick={alPulsar}>
        Guardar
      </Button>,
    );
    const boton = screen.getByRole("button", { name: "Guardar" });

    await userEvent.click(boton);

    expect(boton.getAttribute("aria-busy")).toBe("true");
    expect((boton as HTMLButtonElement).disabled).toBe(true);
    expect(alPulsar).not.toHaveBeenCalled();
  });

  it("en error se marca, y su icono de carga nunca reemplaza la etiqueta", () => {
    render(
      <Button invalid variant="secondary" size="compact">
        Enviar
      </Button>,
    );
    const boton = screen.getByRole("button", { name: "Enviar" });
    expect(boton.getAttribute("data-invalid")).toBe("true");
    expect(boton.getAttribute("type")).toBe("button");
  });

  it("como enlace conserva el aspecto y el nombre", () => {
    render(
      <Button asChild variant="tenant">
        <a href="/destino">Abrir</a>
      </Button>,
    );
    const enlace = screen.getByRole("link", { name: "Abrir" });
    expect(enlace.getAttribute("href")).toBe("/destino");
    expect(enlace.className).toContain("min-h-11");
  });

  it("la accion secundaria de una aseguradora lleva solo su acento: borde y letra, sin relleno", () => {
    render(
      <Button asChild variant="tenant-outline">
        <a href="/llamar">Llamar</a>
      </Button>,
    );
    const enlace = screen.getByRole("link", { name: "Llamar" });
    expect(enlace.className).toContain("border-tenant");
    expect(enlace.className).toContain("text-tenant");
    expect(enlace.className).toContain("bg-transparent");
    expect(enlace.className).not.toMatch(/(^|\s)bg-tenant(\s|$)/);
  });
});

describe("el foco de un campo", () => {
  it("cambia la propia raya al color de foco, sin dibujar otro anillo alrededor", () => {
    render(<Input aria-label="Nombre" />);
    const clases = screen.getByLabelText("Nombre").className;

    // La raya del campo pasa a ser del color de foco --el acento de la aseguradora
    // dentro de su ambito--, y el contorno de 2 px se dibuja hacia adentro, sobre ella.
    expect(clases).toContain("focus-visible:-outline-offset-2");
    expect(clases).toContain("not-aria-invalid:focus-visible:border-focus");
    // Y no hay un anillo aparte por fuera.
    expect(clases).not.toMatch(/(^|\s)focus(-visible)?:(ring|outline-offset-)[^\s]*/);
    expect(clases).not.toContain("focus-visible:outline-offset-2");
  });

  it("un campo con error conserva su raya de peligro aunque tenga el foco", () => {
    render(<Input aria-label="Nombre" invalid />);
    const clases = screen.getByLabelText("Nombre").className;

    expect(clases).toContain("aria-invalid:border-danger");
    expect(clases).toContain("aria-invalid:focus-visible:outline-danger");
  });
});

describe("los campos", () => {
  it("marcan error, carga y deshabilitado para el lector", () => {
    render(
      <>
        <Input aria-label="Nombre" invalid />
        <Textarea aria-label="Comentario" loading />
        <Select aria-label="Idioma" disabled>
          <option value="es">Español</option>
        </Select>
      </>,
    );
    expect(screen.getByLabelText("Nombre").getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByLabelText("Comentario").getAttribute("aria-busy")).toBe("true");
    expect(screen.getByLabelText("Idioma")).toHaveProperty("disabled", true);
  });
});

describe("las piezas de presentacion", () => {
  it("la etiqueta lleva su texto y su tono; el esqueleto esta oculto al lector", () => {
    const { container } = render(
      <>
        <Tag tone="success">Aprobado</Tag>
        <Skeleton className="h-4" />
      </>,
    );
    expect(screen.getByText("Aprobado").className).toContain("text-success");
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });

  it.each(["info", "success", "warning", "danger"] as const)(
    "el aviso en tono %s lleva icono decorativo y texto",
    (tono) => {
      const { container } = render(
        <InlineAlert tone={tono} action={<button type="button">Reintentar</button>}>
          <p>Mensaje</p>
        </InlineAlert>,
      );
      expect(screen.getByText("Mensaje")).toBeDefined();
      expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
      expect(screen.getByRole("button", { name: "Reintentar" })).toBeDefined();
    },
  );

  it.each(["arch", "horizon", "rings"] as const)("el monograma %s es decorativo", (forma) => {
    const { container } = render(<Monogram shape={forma} />);
    const dibujo = container.querySelector("svg");
    expect(dibujo?.getAttribute("aria-hidden")).toBe("true");
    expect(dibujo?.getAttribute("data-monogram")).toBe(forma);
  });
});

describe("las primitivas interactivas", () => {
  it("el plegable abre y cierra con su boton", async () => {
    render(
      <Disclosure>
        <DisclosureTrigger>Detalles</DisclosureTrigger>
        <DisclosureContent>Contenido plegado</DisclosureContent>
      </Disclosure>,
    );
    const disparador = screen.getByRole("button", { name: "Detalles" });
    expect(disparador.getAttribute("aria-expanded")).toBe("false");

    await userEvent.click(disparador);

    expect(disparador.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("Contenido plegado")).toBeDefined();
  });

  it("las pestanas se recorren con las flechas", async () => {
    render(
      <Tabs defaultValue="uno">
        <TabsList aria-label="Secciones">
          <TabsTrigger value="uno">Uno</TabsTrigger>
          <TabsTrigger value="dos">Dos</TabsTrigger>
        </TabsList>
        <TabsContent value="uno">Primera</TabsContent>
        <TabsContent value="dos">Segunda</TabsContent>
      </Tabs>,
    );
    act(() => {
      screen.getByRole("tab", { name: "Uno" }).focus();
    });

    await userEvent.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: "Dos" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("Segunda")).toBeDefined();
  });

  it("el grupo de alternancia marca la opcion, mueve el foco con flechas y elige con Enter", async () => {
    const alCambiar = vi.fn();
    render(
      <SegmentedToggle
        label="Modo"
        value="light"
        onChange={alCambiar}
        options={[
          { value: "light", label: "Claro" },
          { value: "dark", label: "Oscuro", lang: "es" },
        ]}
      />,
    );
    const claro = screen.getByRole("button", { name: "Claro" });
    const oscuro = screen.getByRole("button", { name: "Oscuro" });
    expect(screen.getByRole("group", { name: "Modo" })).toBeDefined();
    expect(claro.getAttribute("aria-pressed")).toBe("true");
    expect(claro.tabIndex).toBe(0);
    expect(oscuro.tabIndex).toBe(-1);

    act(() => {
      claro.focus();
    });
    await userEvent.keyboard("{ArrowLeft}");
    expect(document.activeElement).toBe(oscuro);
    await userEvent.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(claro);
    await userEvent.keyboard("{ArrowUp}");
    await userEvent.keyboard("{Enter}");

    expect(alCambiar).toHaveBeenCalledWith("dark");
    fireEvent.click(claro);
    expect(alCambiar).toHaveBeenCalledTimes(1);
  });
});

describe("el aviso de demostracion", () => {
  const completo = (t: ReturnType<typeof createTranslate>) => t("home.demo_line");
  const corto = (t: ReturnType<typeof createTranslate>) => t("home.insurers.title");

  it("es una region con nombre, no una region en vivo", () => {
    render(
      <LocaleProvider initial={{ locale: "es", source: "device" }}>
        <DemoNotice message={completo} />
      </LocaleProvider>,
    );
    const region = screen.getByRole("region", { name: createTranslate("es")("demo.notice.label") });
    expect(region.getAttribute("aria-live")).toBeNull();
    expect(region.textContent).toContain(createTranslate("es")("home.demo_line"));
  });

  it("compacto muestra la linea corta y abre el texto completo en su sitio", async () => {
    const en = createTranslate("en");
    render(
      <LocaleProvider initial={{ locale: "en", source: "device" }}>
        <DemoNotice message={completo} shortMessage={corto} compact />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("demo-notice").textContent).toContain(en("home.insurers.title"));

    await userEvent.click(screen.getByRole("button", { name: en("demo.notice.more") }));

    expect(screen.getByTestId("demo-notice").textContent).toContain(en("home.demo_line"));
    expect(
      screen.getByRole("button", { name: en("demo.notice.less") }).getAttribute("aria-expanded"),
    ).toBe("true");
  });
});
