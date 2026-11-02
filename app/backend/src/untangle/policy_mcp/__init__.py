"""Servidor MCP propio de los datos rigidos de una poliza (plan 09, punto 6, 2026-11-02).

Publica `untangle.policy_rag.facts` como herramientas del Model Context Protocol, para que
cualquier cliente MCP --Claude Desktop, otro agente-- consulte la poliza de ejemplo de una
aseguradora: resumen y vigencia, limites, deducibles, vehiculos, conductores, endosos y una
clausula por su identificador. Solo lectura, solo datos sinteticos, y por el mismo punto unico de
sesion que el resto del aplicativo (`tenancy.session_for` fija el `tenant_id` y la politica de fila
hace el resto).

La superficie esta en `server.py` (`build_server`) y el proceso en `__main__.py`
(`mise run mcp`, transporte stdio).
"""
