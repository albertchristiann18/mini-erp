from django.http import JsonResponse

def api_root(request):
    return JsonResponse({
        "status": "ok",
        "message": "Welcome to the mini-ERP API. Access documentation at /docs/.",
        "endpoints": ["/admin/", "/api/inventory/"]
    })