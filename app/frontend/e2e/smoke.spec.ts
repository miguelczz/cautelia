// La prueba de humo de la bandeja, contra el aplicativo corriendo (`mise run smoke`).
//
// **Que comprueba y que no.** Comprueba que el recorrido funciona de punta a punta con
// datos sembrados de verdad: la cola trae casos, el orden es el del servidor, los filtros
// viven en la direccion, la vista reune sus seis bloques, los tres plegados dicen su
// resultado sin abrirlos, y una decision sin comentario se rechaza sin perder lo escrito.
//
// **No** sustituye a nada: las reglas las prueban las 102 de integracion y las 82 de
// pantalla, con dobles y en aislamiento. Esta responde otra pregunta, la que ninguna de
// ellas responde: *lo que esta corriendo en esta maquina, ahora, con esta base, ¿sirve?*
// Es la que encuentra la clave que falta, el puerto equivocado y la migracion sin subir.

import { expect, test } from "@playwright/test";

import { ASEGURADORA } from "./smoke.config";

const COLA = `/t/${ASEGURADORA}/inbox`;

/** Las filas de la tabla sin su encabezado. */
function filas(page: import("@playwright/test").Page) {
  return page.getByRole("row").filter({ has: page.getByRole("link") });
}

/**
 * Cuantas filas hay, **esperando a que la lista este dibujada**.
 *
 * Contar justo despues de navegar cuenta cero: la cola pide sus casos al servidor y las
 * filas llegan en un dibujo posterior. Es la forma once del catalogo de revision --leer
 * el efecto en el mismo instante que se provoca-- y esta prueba la cometio en su primera
 * version: `todas` valia cero y "filtrar quito filas" pasaba al reves.
 */
async function cuantasFilas(page: import("@playwright/test").Page): Promise<number> {
  await expect(page.getByTestId("inbox-queue")).toBeVisible();
  // O hay filas, o hay un aviso de lista vacia. Las dos son estados dibujados; lo que no
  // vale es contar mientras todavia no hay ninguno de los dos.
  await expect
    .poll(async () => (await filas(page).count()) + (await page.getByTestId("queue-empty").count()))
    .toBeGreaterThan(0);
  return filas(page).count();
}

test("la cola trae casos y los ordena como los ordeno el servidor", async ({ page }) => {
  await page.goto(COLA);

  const cuantos = await cuantasFilas(page);
  expect(cuantos, "la cola llego vacia: siembra con `mise run synthetic:seed`").toBeGreaterThan(0);
  const lista = filas(page);

  // El orden lo decide el servidor: prioridad primero. La primera fila no puede ser de
  // prioridad normal si hay alguna alta en la pagina.
  const textos = await lista.allInnerTexts();
  const primeraAlta = textos.findIndex((t) => t.includes("Alta") || t.includes("High"));
  if (primeraAlta >= 0) {
    expect(primeraAlta, "una fila de prioridad normal quedo delante de una alta").toBe(0);
  }
});

test("un filtro viaja en la direccion y cambia la lista", async ({ page }) => {
  await page.goto(COLA);
  const todas = await cuantasFilas(page);

  await page.goto(`${COLA}?state=derived`);
  const cuantos = await cuantasFilas(page);

  expect(cuantos, "filtrar por derivados no quito ninguna fila").toBeLessThan(todas);
  expect(cuantos, "filtrar por derivados no dejo ninguna fila").toBeGreaterThan(0);
  // Y la direccion lo conserva: recargar no pierde el filtro.
  await page.reload();
  await expect(filas(page)).toHaveCount(cuantos);
});

test("un filtro sin resultados lo dice y ofrece quitarlo", async ({ page }) => {
  // Una lista vacia sin explicacion se lee como una bandeja vacia, que es lo contrario.
  await page.goto(`${COLA}?state=open&priority=high`);

  const aviso = page.getByTestId("queue-empty");
  await expect(aviso).toBeVisible();
  await expect(aviso.getByRole("button")).toBeVisible();

  await aviso.getByRole("button").click();
  await expect(page).toHaveURL(new RegExp(`${COLA}/?$`));
  expect(await cuantasFilas(page)).toBeGreaterThan(0);
});

test("la vista de un caso derivado reune sus bloques", async ({ page }) => {
  await page.goto(`${COLA}?state=derived`);
  await cuantasFilas(page);
  await filas(page).first().getByRole("link").click();

  // El encabezado, con las cuatro cosas juntas y las acciones al lado (BR2.1).
  const encabezado = page.getByTestId("case-header");
  await expect(encabezado).toBeVisible();
  await expect(encabezado.getByTestId("case-reason")).not.toBeEmpty();
  await expect(encabezado.getByTestId("case-completeness")).not.toBeEmpty();
  await expect(encabezado.getByTestId("case-decided-by")).not.toBeEmpty();
  await expect(encabezado.getByTestId("decision-form")).toBeVisible();

  // Los tres primeros siempre; los tres ultimos dicen su resultado en una frase y van abiertos
  // (2026-10-12), y el que no tiene dato que decir no se pinta.
  for (const abierto of ["block-fields", "block-transcript", "block-citations"]) {
    await expect(page.getByTestId(abierto)).toBeVisible();
  }
  for (const bloque of ["block-rule", "block-controls", "block-trace"]) {
    const dibujado = page.getByTestId(bloque);
    if ((await dibujado.count()) > 0) {
      await expect(dibujado, `${bloque} esta dibujado y no dice nada`).not.toBeEmpty();
      await expect(
        dibujado.locator("[aria-expanded]"),
        `${bloque} se pliega y esconde su contenido`,
      ).toHaveCount(0);
    }
  }
});

test("una decision sin comentario se rechaza y no pierde lo escrito", async ({ page }) => {
  await page.goto(`${COLA}?state=derived`);
  await cuantasFilas(page);
  await filas(page).first().getByRole("link").click();
  await expect(page.getByTestId("case-header")).toBeVisible();

  const acciones = page.getByTestId("decision-form").getByRole("button");
  await acciones.first().click();

  // El servidor la rechaza --la validacion no se reimplementa en la pantalla-- y lo que
  // se intento sigue marcado.
  await expect(page.getByTestId("decision-problem")).toBeVisible();
  await expect(acciones.first()).toHaveAttribute("data-attempted", "true");
});

test("una decision con comentario cierra el caso y lo saca de la cola", async ({ page }) => {
  test.skip(
    process.env.UNTANGLE_SMOKE_DECIDE !== "1",
    "decidir cierra el caso y no vuelve a 'derivado': se pide con UNTANGLE_SMOKE_DECIDE=1",
  );

  await page.goto(`${COLA}?state=derived`);
  const antes = await cuantasFilas(page);
  const fila = filas(page).first();
  // El numero del caso, de su primera linea. Si la fila llegara sin texto, la prueba
  // seguiria comprobando el recuento pero dejaria de comprobar **cual** se fue: eso es
  // un fallo, no un caso que se salta.
  const numero = (await fila.innerText()).split("\n").at(0) ?? "";
  expect(numero, "la fila llego sin numero de caso").not.toBe("");
  await fila.getByRole("link").click();

  await page.getByLabel(/Tu nota|Your note/).fill("Prueba de humo: cubierto segun la poliza.");
  await page.getByTestId("decision-form").getByRole("button").first().click();

  // El caso queda cerrado y **se va solo de la cola**, por el flujo de avisos.
  await expect(page.getByTestId("case-resolution")).toBeVisible();
  await page.goto(`${COLA}?state=derived`);
  await expect(filas(page)).toHaveCount(antes - 1);
  await expect(page.getByText(numero)).toHaveCount(0);
});

// --- El chat: lo que hace un visitante, y lo unico que la pagina de inicio ofrece ---

// Lo que escribe el visitante de esta prueba. Pide hablar con una persona: es una
// senal que los controles reconocen con sus patrones versionados, asi que el turno
// deriva **sin llamar al modelo**. Cualquier otro texto gastaria cuota.
const MENSAJE = "Quiero hablar con una persona";

test("el chat responde al primer mensaje de un visitante", async ({ page }) => {
  // **La razon de que este paso exista.** El chat no podia atender a nadie: el canal
  // entregaba el turno sin caso, el grafo lo rechazaba, la excepcion moria en una
  // tarea que nadie esperaba y la pantalla se quedaba muda con un `202` delante.
  // Las 2.363 pruebas pasaban porque todas enchufan un doble del grafo.
  await page.goto(`/t/${ASEGURADORA}/chat`);

  // La lista **no** se comprueba visible: nace vacia, y un `ol` sin hijos no tiene
  // alto, asi que "visible" seria falso en una pagina que funciona. Lo que dice que
  // la pagina esta en pie es su compositor.
  const transcripcion = page.getByTestId("chat-transcript");
  const escrito = page.getByLabel(/Tu mensaje|Your message/);
  await expect(escrito).toBeVisible();

  // **Se espera a que el flujo este conectado antes de escribir.** Un mensaje que
  // llega antes de que su flujo exista ya se atiende --la respuesta espera en una cola
  // reservada y queda su evento `chat.message_before_stream`--, pero esta prueba mide
  // el chat y no esa carrera. Una persona rara vez la gana; Playwright si.
  await expect(page.getByText(/Conectando|Connecting/)).toHaveCount(0);
  await escrito.fill(MENSAJE);
  await page.getByRole("button", { name: /Enviar|Send/ }).click();

  // **Se afirma la frase de la derivacion, y a proposito.** Contar turnos no sirve:
  // la divulgacion de apertura sale una sola vez por conversacion, asi que el
  // recuento depende de si esta cookie ya habia escrito antes; y "la ultima es de la
  // agente" pasaria igual con la divulgacion llegando tarde y ninguna respuesta. Esta
  // es la unica asercion que distingue *atendio el turno* de *dijo algo*.
  const derivacion = transcripcion.locator("li").filter({ hasText: /un ajustador|an adjuster/i });
  await expect(derivacion, "la agente no respondio al mensaje del visitante").toHaveCount(1, {
    timeout: 15_000,
  });

  // Y el mensaje del visitante quedo en la conversacion.
  await expect(transcripcion.locator("li").filter({ hasText: MENSAJE })).toHaveCount(1);
});
