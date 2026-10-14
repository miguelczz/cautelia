// Probar el microfono sin llamar a nadie (2026-10-09).
//
// La llamada abria el microfono sin error y mandaba audio en silencio (pico 0,0004),
// y cada intento gastaba una llamada. Esto lo prueba gratis: abre el microfono con
// las mismas correcciones y por el **mismo camino** que la llamada --un
// `AudioContext` a 24 kHz y el mismo procesador de captura--, dice cual microfono
// esta usando el navegador y si le llega sonido, y deja elegir otro. La llamada usa
// el que quede elegido. Nada sale del navegador.

import { MicrophoneIcon } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { Select } from "../../shared/ui/select";
import { AYUDA_DE_LLAMADA } from "./call-helper-style";
import {
  CAPTURE_WORKLET,
  chooseMicrophone,
  chosenMicrophone,
  SAMPLE_RATE,
} from "./voice-transport";

/** Por debajo de esto, en la prueba, no llega sonido: el umbral de la llamada. */
const AUDIBLE = 0.0003;
/** Cuanto escucha la prueba. */
const DURACION_MS = 5_000;

interface Device {
  readonly id: string;
  readonly label: string;
}

interface Result {
  readonly label: string;
  readonly peak: number;
  readonly muted: boolean;
  readonly deviceRate: number | null;
}

async function inputs(): Promise<Device[]> {
  const todos = await navigator.mediaDevices.enumerateDevices();
  return todos
    .filter((d) => d.kind === "audioinput" && d.deviceId !== "")
    .map((d) => ({ id: d.deviceId, label: d.label }));
}

async function listen(deviceId: string | null, onLevel: (level: number) => void): Promise<Result> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      ...(deviceId === null ? {} : { deviceId: { exact: deviceId } }),
    },
  });
  const [pista] = stream.getAudioTracks();
  const contexto = new AudioContext({ sampleRate: SAMPLE_RATE });
  let pico = 0;
  try {
    if (contexto.state === "suspended") {
      await contexto.resume().catch(() => undefined);
    }
    await contexto.audioWorklet.addModule(CAPTURE_WORKLET);
    const captura = new AudioWorkletNode(contexto, "voice-capture");
    captura.port.onmessage = (evento: MessageEvent<{ level: number }>) => {
      pico = Math.max(pico, evento.data.level);
      onLevel(evento.data.level);
    };
    contexto.createMediaStreamSource(stream).connect(captura);
    await new Promise((listo) => setTimeout(listo, DURACION_MS));
    return {
      label: pista?.label ?? "",
      peak: pico,
      muted: pista?.muted ?? false,
      deviceRate: pista?.getSettings().sampleRate ?? null,
    };
  } finally {
    for (const p of stream.getTracks()) {
      p.stop();
    }
    await contexto.close().catch(() => undefined);
  }
}

export function MicCheck() {
  const { t } = useLocale();
  const [estado, setEstado] = useState<"idle" | "listening" | "done" | "failed">("idle");
  const [nivel, setNivel] = useState(0);
  const [resultado, setResultado] = useState<Result | null>(null);
  const [dispositivos, setDispositivos] = useState<Device[]>([]);
  const [elegido, setElegido] = useState<string | null>(() => chosenMicrophone());
  const vivo = useRef(true);

  useEffect(
    () => () => {
      vivo.current = false;
    },
    [],
  );

  async function probar(deviceId: string | null) {
    setEstado("listening");
    setResultado(null);
    try {
      const r = await listen(deviceId, (valor) => {
        if (vivo.current) {
          setNivel(valor);
        }
      });
      // Los nombres de los microfonos solo se leen con el permiso ya concedido.
      const lista = await inputs();
      if (!vivo.current) {
        return;
      }
      setResultado(r);
      setDispositivos(lista);
      setEstado("done");
    } catch {
      if (vivo.current) {
        setEstado("failed");
      }
    }
  }

  const llega = resultado !== null && resultado.peak >= AUDIBLE;

  return (
    <div className="flex w-full flex-col items-center gap-3" data-testid="mic-check">
      <Button
        type="button"
        variant="secondary"
        size="compact"
        className={AYUDA_DE_LLAMADA}
        disabled={estado === "listening"}
        onClick={() => void probar(elegido)}
      >
        <MicrophoneIcon aria-hidden="true" size={18} className="text-tenant" />
        {estado === "listening" ? t("voice.mic_check.listening") : t("voice.mic_check.start")}
      </Button>
      {estado === "listening" ? (
        <div aria-hidden="true" className="h-1.5 w-full max-w-xs rounded-pill bg-surface-alt">
          <div
            className="h-1.5 rounded-pill bg-tenant transition-[width] duration-100"
            style={{ width: `${String(Math.min(100, Math.round(nivel * 400)))}%` }}
          />
        </div>
      ) : null}
      {estado === "failed" ? (
        <p role="status" className="text-center text-small text-fg">
          {t("voice.mic_check.failed")}
        </p>
      ) : null}
      {resultado === null ? null : (
        <div
          role="status"
          className="flex w-full flex-col items-center gap-2 rounded-surface bg-selected p-4 text-center text-small text-fg"
        >
          <p>{t("voice.mic_check.device", { device: resultado.label || "—" })}</p>
          <p className="font-medium">
            {llega ? t("voice.mic_check.ok") : t("voice.mic_check.silent")}
          </p>
          <p className="text-caption text-fg-secondary" data-testid="mic-check-detail">
            {t("voice.mic_check.detail", {
              peak: resultado.peak.toFixed(4),
              rate: resultado.deviceRate === null ? "—" : String(resultado.deviceRate),
              muted: resultado.muted
                ? t("voice.mic_check.answer_yes")
                : t("voice.mic_check.answer_no"),
            })}
          </p>
          {dispositivos.length > 1 ? (
            <label className="flex w-full max-w-xs flex-col gap-1">
              <span>{t("voice.mic_check.choose")}</span>
              <Select
                value={elegido ?? ""}
                onChange={(evento) => {
                  const valor = evento.target.value === "" ? null : evento.target.value;
                  setElegido(valor);
                  chooseMicrophone(valor);
                  void probar(valor);
                }}
              >
                <option value="">{t("voice.mic_check.browser_default")}</option>
                {dispositivos.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.label || d.id}
                  </option>
                ))}
              </Select>
            </label>
          ) : null}
        </div>
      )}
    </div>
  );
}
