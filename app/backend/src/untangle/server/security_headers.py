"""El conjunto unico de cabeceras de seguridad (BR6.2, SEC-U6.1, CG-U6-2, CG-U6-3).

Toda respuesta del proceso lo lleva --la aplicacion, los estaticos, la API y
los errores, incluido el no previsto-- y es **uno solo**: ninguna ruta tiene el
suyo. Cuando U16 abra el microfono para la consola de voz, lo abrira aqui, en
este mismo conjunto, y no con una cabecera propia.

## La politica de contenido (CG-U6-2)

Todo desde el propio origen (SEC-U6.2) y **sin ninguna excepcion para scripts**:
ni `unsafe-inline`, ni `unsafe-eval`, ni huellas que regenerar. El paso que
aplica el modo claro u oscuro antes de pintar es un archivo propio y pequeno
(`/theme-boot.js`, CG-U6-1), no un script en linea, y por eso `script-src 'self'`
basta. Las imagenes admiten ademas `data:` para los iconos que el compilador
incrusta. Los marcos ajenos no pueden incrustar ninguna pagina
(`frame-ancestors 'none'`).

## El resto (CG-U6-3)

- `X-Content-Type-Options: nosniff`: el navegador no adivina el tipo.
- `Referrer-Policy: strict-origin-when-cross-origin`: hacia fuera sale como
  mucho el origen, nunca la ruta, que puede nombrar un caso.
- `Permissions-Policy`: se niega lo que el aplicativo no usa --camara,
  ubicacion y pagos-- y el microfono se permite **solo al propio origen**: la
  llamada de U16 lo pide con `getUserMedia`, y con `microphone=()` el navegador
  lo niega aunque la persona lo haya permitido para el sitio (el defecto que
  Miguel vio el 2026-10-06: "este navegador no dio acceso al microfono" con el
  permiso concedido).
- `Strict-Transport-Security`: **solo** cuando la peticion llega por HTTPS. Por
  HTTP no significa nada y el navegador la ignora; mandarla ahi solo confundiria
  a quien lea las cabeceras.
"""

from __future__ import annotations

#: La politica de seguridad de contenido de CG-U6-2, directiva por directiva.
CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    )
)

#: Lo que el aplicativo no usa, negado; el microfono, solo para este origen (U16).
PERMISSIONS_POLICY = "camera=(), microphone=(self), geolocation=(), payment=()"

#: Un ano, para el propio origen y sus subdominios. Sin `preload`: entrar en esa
#: lista es una decision del dominio publico, que es del intent `infra`.
STRICT_TRANSPORT_SECURITY = "max-age=31536000; includeSubDomains"

#: Las cabeceras que lleva **toda** respuesta.
SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    ("Content-Security-Policy", CONTENT_SECURITY_POLICY),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ("Permissions-Policy", PERMISSIONS_POLICY),
)


def headers_for(*, https: bool) -> tuple[tuple[str, str], ...]:
    """El conjunto para una respuesta: el de siempre, y el transporte si es HTTPS."""
    if https:
        return (*SECURITY_HEADERS, ("Strict-Transport-Security", STRICT_TRANSPORT_SECURITY))
    return SECURITY_HEADERS
