// La decision de un caso, con su comentario obligatorio (BR4.1, BR4.4, BR5.4).
//
// **Un boton por accion, y no un grupo de opciones con un boton de confirmar.** Las
// tres razones aparecieron juntas: un `input type="radio"` mide 13 x 13 y el arnes
// exige 44 x 44 en cualquier control tactil (BR7.3 de U6); un grupo de radios es **una sola
// parada de tabulacion**, asi que el recorrido con Tab no llega a las demas opciones; y
// un grupo de opciones necesita una elegida por omision, que en un formulario de
// decision significa dejar "aprobar" preseleccionado. Con un boton por accion no hay
// nada preseleccionado, cada uno es su propia parada y el primitivo `Button` ya
// garantiza el tamano.
//
// **Lo que se escribio no se pierde, y la accion intentada se sigue viendo.** Ni cuando
// el servidor rechaza la decision por falta de comentario, ni cuando otra persona
// decidio antes, ni cuando el enlace vence a mitad de la frase: el texto sigue en el
// campo y el boton que se pulso queda marcado como el intentado. Perder lo escrito por
// un error de validacion es la forma mas barata de que alguien decida sin comentario a
// la segunda, y en el caso del enlace vencido convierte un vencimiento en trabajo
// perdido justo para quien estaba terminando.
//
// **La validacion no se reimplementa aqui.** El comentario obligatorio lo exige el
// servidor y el mensaje sale del catalogo por su codigo de error: una segunda validacion
// en el navegador es una segunda definicion de lo que es valido, y el dia que una cambie
// la otra sigue diciendo lo de antes. Por eso los botones **no se deshabilitan** con el
// campo vacio: se envia, el servidor responde y la pantalla dice lo que respondio.
//
// **Las acciones no se deducen aqui.** Llegan resueltas del servidor, que las decide por
// la configuracion de la aseguradora y el estado del caso (BR4.5, BR4.3). Una pantalla
// que preguntara "es una agencia?" escribiria esa regla por segunda vez.

import { useState } from "react";

import type { InboxAction } from "../../shared/api-client/inbox";
import type { ProblemView } from "../../shared/api-client/problems";
import { useLocale } from "../../shared/i18n/locale-provider";
import { Button } from "../../shared/ui/button";
import { InlineAlert } from "../../shared/ui/inline-alert";
import { Textarea } from "../../shared/ui/textarea";
import { actionLabel } from "./inbox-labels";

export interface DecisionFormProps {
  /** Las acciones que el servidor dice que este caso ofrece ahora. */
  readonly actions: readonly InboxAction[];
  /** Lo que la pantalla hace al confirmar. Devuelve el error, si lo hubo. */
  readonly onSubmit: (action: InboxAction, comment: string) => Promise<ProblemView | null>;
  /** El identificador del formulario, para que dos en una pagina no compartan `id`. */
  readonly idPrefix: string;
}

export function DecisionForm({ actions, onSubmit, idPrefix }: DecisionFormProps) {
  const { t } = useLocale();
  const [intentada, setIntentada] = useState<InboxAction | null>(null);
  const [nota, setNota] = useState("");
  const [problema, setProblema] = useState<ProblemView | null>(null);
  const [enviando, setEnviando] = useState(false);

  if (actions.length === 0) {
    return null;
  }

  const confirmar = async (accion: InboxAction): Promise<void> => {
    setIntentada(accion);
    setEnviando(true);
    const fallo = await onSubmit(accion, nota);
    setEnviando(false);
    // El texto y la accion intentada **siguen aqui**: nada de `setNota("")` en el
    // camino del error. Al acertar, la pantalla de arriba deja de dibujar este
    // formulario, asi que tampoco hay nada que limpiar.
    setProblema(fallo);
  };

  const idError = `${idPrefix}-decision-problem`;

  return (
    <form className="flex flex-col gap-3" data-testid="decision-form">
      <label htmlFor={`${idPrefix}-comment`} className="text-caption text-fg-secondary">
        {t("inbox.decision.comment_label")}
      </label>
      <Textarea
        id={`${idPrefix}-comment`}
        rows={3}
        value={nota}
        invalid={problema !== null}
        {...(problema === null ? {} : { "aria-describedby": idError })}
        onChange={(evento) => {
          setNota(evento.target.value);
        }}
      />
      <p className="text-caption text-fg-secondary">{t("inbox.decision.comment_hint")}</p>

      {problema === null ? null : (
        <InlineAlert tone="danger" role="alert" id={idError} data-testid="decision-problem">
          {problema.message(t)}
        </InlineAlert>
      )}

      <div className="flex flex-wrap gap-2" role="group" aria-label={t("inbox.decision.title")}>
        {actions.map((accion) => (
          <Button
            key={accion}
            type="button"
            // El que se intento queda destacado: es lo que hace visible que "la
            // decision elegida sigue en pantalla" cuando el servidor la rechaza.
            variant={intentada === accion ? "primary" : "secondary"}
            data-attempted={intentada === accion || undefined}
            disabled={enviando}
            onClick={() => {
              void confirmar(accion);
            }}
          >
            {actionLabel(accion)(t)}
          </Button>
        ))}
      </div>
    </form>
  );
}
