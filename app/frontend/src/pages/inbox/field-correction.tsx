// La correccion de un campo, en linea y dentro del bloque de completitud
// (BR3.1 a BR3.4).
//
// **El valor anterior se conserva.** Un intento fallido no borra un dato bueno: lo
// que la pantalla hace al ser rechazada es decir el mensaje del servidor y dejar el
// campo como estaba. El valor que se ve escrito es el que se intento, para
// corregirlo sin volver a teclearlo.
//
// **La validacion es la de U4 y no se reimplementa**: la pantalla marca el campo y
// muestra el mensaje que el servidor devuelve, con el campo y el formato esperado.
// Una segunda validacion en el navegador es una segunda definicion de lo que es
// valido.
//
// **Un caso cerrado no ofrece esta accion** y la peticion directa se rechaza igual:
// lo segundo es lo que de verdad lo impide, y quien decide si se ofrece es el
// servidor, que lo manda resuelto. La pantalla no vuelve a preguntarse si el caso
// esta cerrado.

import { useState } from "react";

import type { CaseFieldView } from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { Input } from "../../shared/ui/input";
import { fieldLabel } from "./inbox-labels";

export interface FieldCorrectionProps {
  readonly field: CaseFieldView;
  /** Lo que la pantalla hace al guardar. Devuelve el error, si lo hubo. */
  readonly onSave: (fieldKey: string, value: string) => Promise<ProblemView | null>;
}

export function FieldCorrection({ field, onSave }: FieldCorrectionProps) {
  const { t } = useLocale();
  const [abierto, setAbierto] = useState(false);
  const [valor, setValor] = useState("");
  const [problema, setProblema] = useState<ProblemView | null>(null);
  const [guardado, setGuardado] = useState(false);
  const id = `correct-${field.field_key}`;

  if (!abierto) {
    return (
      <span className="flex items-center gap-2">
        <Button
          variant="ghost"
          onClick={() => {
            setAbierto(true);
            setGuardado(false);
          }}
        >
          {t("inbox.correction.edit", { field: fieldLabel(field.label_key)(t) })}
        </Button>
        {guardado ? (
          <span role="status" className="text-caption text-fg-secondary">
            {t("inbox.correction.saved")}
          </span>
        ) : null}
      </span>
    );
  }

  const guardar = async (): Promise<void> => {
    const fallo = await onSave(field.field_key, valor);
    setProblema(fallo);
    if (fallo === null) {
      // Solo al acertar se cierra y se limpia: al fallar, lo escrito se queda para
      // corregirlo sin volver a teclearlo.
      setAbierto(false);
      setValor("");
      setGuardado(true);
    }
  };

  return (
    <form
      className="flex w-full flex-col gap-2"
      data-testid={`correction-${field.field_key}`}
      onSubmit={(evento) => {
        evento.preventDefault();
        void guardar();
      }}
    >
      <label htmlFor={id} className="text-caption text-fg-secondary">
        {t("inbox.correction.value_label")}
      </label>
      <Input
        id={id}
        value={valor}
        invalid={problema !== null}
        onChange={(evento) => {
          setValor(evento.target.value);
        }}
      />
      {problema === null ? null : (
        <InlineAlert
          tone="danger"
          role="alert"
          data-testid={`correction-problem-${field.field_key}`}
        >
          {problema.message(t)}
        </InlineAlert>
      )}
      <span className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary">
          {t("inbox.correction.save")}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            setAbierto(false);
            setProblema(null);
          }}
        >
          {t("inbox.correction.cancel")}
        </Button>
      </span>
    </form>
  );
}
