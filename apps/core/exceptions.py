from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Render every DRF error as {"detail": str, "errors": {...}} for the UI."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and "detail" in data:
        response.data = {"detail": str(data["detail"]), "errors": {}}
    elif isinstance(data, dict):
        response.data = {"detail": "Invalid request.", "errors": data}
    else:
        response.data = {"detail": "Invalid request.", "errors": {"non_field": data}}
    return response
