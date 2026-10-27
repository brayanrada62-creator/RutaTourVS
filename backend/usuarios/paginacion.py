"""Búsqueda y paginación opcionales para los listados.

Sin ?page= la lista responde igual que siempre, así Android y Angular no se rompen.
Con ?page=1&page_size=12 responde {"count": total, "results": [...]}.
"""
from drf_yasg import openapi

PARAMETROS_LISTA = [
    openapi.Parameter("search", openapi.IN_QUERY, description="Texto a buscar", type=openapi.TYPE_STRING),
    openapi.Parameter("page", openapi.IN_QUERY, description="Número de página (activa la paginación)", type=openapi.TYPE_INTEGER),
    openapi.Parameter("page_size", openapi.IN_QUERY, description="Registros por página (por defecto 12, máximo 100)", type=openapi.TYPE_INTEGER),
]


def texto_busqueda(request):
    return (request.query_params.get("search") or "").strip()


def entero_query(request, nombre):
    valor = request.query_params.get(nombre)
    if valor in (None, ""):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def paginar(request, registros, convertir):
    """registros: queryset (ya ordenado) o lista. convertir: función que arma el diccionario de cada uno."""
    if "page" not in request.query_params:
        return [convertir(r) for r in registros]
    try:
        pagina = max(int(request.query_params["page"]), 1)
        tamano = min(max(int(request.query_params.get("page_size", 12)), 1), 100)
    except ValueError:
        pagina, tamano = 1, 12
    total = registros.count() if hasattr(registros, "model") else len(registros)
    inicio = (pagina - 1) * tamano
    return {"count": total, "results": [convertir(r) for r in registros[inicio:inicio + tamano]]}
