// Dos plugins de ESLint sin tipos propios. Se declaran aqui, acotados y con su
// razon, en vez de apagar la comprobacion de tipos del archivo de configuracion:
// lo que se pierde es el tipado de esos dos objetos, no el del resto.

declare module "eslint-plugin-security" {
  const plugin: {
    configs: { recommended: import("eslint").Linter.Config };
  };
  export default plugin;
}

declare module "eslint-plugin-jsx-a11y" {
  const plugin: {
    flatConfigs: { strict: import("eslint").Linter.Config };
  };
  export default plugin;
}
