// El credito del pie: quien hizo la demostracion y sus dos perfiles.
//
// Los perfiles son enlaces de texto con su icono, sin borde ni forma de boton (decision
// de Miguel, 2026-10-07): al pasar el puntero o enfocarlos, el icono sube un poco y una
// linea crece bajo el nombre. Con movimiento reducido no hay desplazamiento ni
// crecimiento: la linea aparece de golpe y solo cambia el color. Cada enlace mide 44 de
// alto (BR7.3); su nombre accesible es siempre el completo, con el nombre de la persona
// y la red, y avisa que se abre en pestana nueva (BR7.7). En telefono solo se ve el icono.

import { GithubLogoIcon, LinkedinLogoIcon } from "@phosphor-icons/react";

import { useLocale } from "../../shared/i18n/locale-provider";
import { AUTHOR } from "../../shared/site/author";

const ENLACE =
  "group inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-control px-1 text-small text-fg-secondary no-underline transition-colors duration-[160ms] ease-out hover:text-fg";
const ICONO =
  "motion-safe:transition-transform motion-safe:duration-[160ms] motion-safe:ease-out motion-safe:group-hover:-translate-y-0.5";
const SUBRAYADO =
  "hidden bg-[linear-gradient(currentColor,currentColor)] bg-[length:0%_1px] bg-left-bottom bg-no-repeat pb-px group-hover:bg-[length:100%_1px] motion-safe:transition-[background-size] motion-safe:duration-200 motion-safe:ease-out tablet:inline";

export function AuthorCredit() {
  const { t } = useLocale();
  const perfiles = [
    {
      id: "linkedin",
      href: AUTHOR.linkedinUrl,
      icon: <LinkedinLogoIcon aria-hidden="true" focusable="false" size={18} className={ICONO} />,
      text: t("shell.footer.linkedin"),
      label: t("shell.footer.linkedin_label", { name: AUTHOR.name }),
    },
    {
      id: "github",
      href: AUTHOR.githubUrl,
      icon: <GithubLogoIcon aria-hidden="true" focusable="false" size={18} className={ICONO} />,
      text: t("shell.footer.github"),
      label: t("shell.footer.github_label", { name: AUTHOR.name }),
    },
  ];

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="site-author">
      <p>{t("shell.footer.made_by", { name: AUTHOR.name })}</p>
      <ul className="inline-flex items-center gap-1">
        {perfiles.map((perfil) => (
          <li key={perfil.id}>
            <a
              href={perfil.href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={perfil.label}
              data-profile={perfil.id}
              className={ENLACE}
            >
              {perfil.icon}
              <span className={SUBRAYADO}>{perfil.text}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
