import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../app/testing";
import { createTranslate } from "../../shared/i18n/translate";
import { MicCheck } from "./mic-check";
import { chosenMicrophone } from "./voice-transport";

const es = createTranslate("es");

/** Un `AudioContext` de mentira cuyo procesador de captura entrega `niveles`. */
function audioDeMentira(niveles: readonly number[]) {
  class Nodo {
    port: { onmessage: ((e: { data: { level: number } }) => void) | null } = { onmessage: null };
    connect() {
      return this;
    }
  }
  class Contexto {
    state = "running";
    audioWorklet = { addModule: () => Promise.resolve() };
    createMediaStreamSource() {
      return {
        connect: (nodo: Nodo) => {
          for (const nivel of niveles) {
            nodo.port.onmessage?.({ data: { level: nivel } });
          }
        },
      };
    }
    resume() {
      return Promise.resolve();
    }
    close() {
      return Promise.resolve();
    }
  }
  vi.stubGlobal("AudioContext", Contexto);
  vi.stubGlobal("AudioWorkletNode", Nodo);
}

function microfonoDeMentira(etiqueta: string) {
  const pista = {
    label: etiqueta,
    muted: false,
    stop: vi.fn(),
    getSettings: () => ({ sampleRate: 48000 }),
  };
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia: vi.fn(() =>
        Promise.resolve({ getAudioTracks: () => [pista], getTracks: () => [pista] }),
      ),
      enumerateDevices: vi.fn(() =>
        Promise.resolve([
          { kind: "audioinput", deviceId: "mac", label: "MacBook Air Microphone" },
          { kind: "audioinput", deviceId: "teams", label: "Microsoft Teams Audio" },
        ]),
      ),
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("probar el microfono sin llamar", () => {
  it("dice que microfono usa el navegador y que no llega sonido, y deja elegir otro", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    audioDeMentira([0, 0.0001, 0.0002]);
    microfonoDeMentira("Microsoft Teams Audio");
    renderWithProviders(<MicCheck />);

    await userEvent.click(screen.getByRole("button", { name: es("voice.mic_check.start") }));
    await vi.advanceTimersByTimeAsync(5_500);

    expect(
      await screen.findByText(es("voice.mic_check.device", { device: "Microsoft Teams Audio" })),
    ).toBeTruthy();
    expect(screen.getByText(es("voice.mic_check.silent"))).toBeTruthy();

    await userEvent.selectOptions(screen.getByRole("combobox"), "mac");
    expect(chosenMicrophone()).toBe("mac");
  });

  it("con voz en el microfono dice que la llamada te va a oir", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    audioDeMentira([0.01, 0.2]);
    microfonoDeMentira("MacBook Air Microphone");
    renderWithProviders(<MicCheck />);

    await userEvent.click(screen.getByRole("button", { name: es("voice.mic_check.start") }));
    await vi.advanceTimersByTimeAsync(5_500);

    expect(await screen.findByText(es("voice.mic_check.ok"))).toBeTruthy();
  });
});
