from django.shortcuts import render
import logging

logger = logging.getLogger(__name__)

def custom_404_view(request, exception):
    logger.warning(f"404 Not Found: {request.path}")
    return render(request, 'errors/404.html', status=404)

def custom_500_view(request):
    logger.error(f"500 Internal Server Error at: {request.path if hasattr(request, 'path') else 'unknown'}")
    return render(request, 'errors/500.html', status=500)

def custom_403_view(request, exception):
    logger.warning(f"403 Forbidden: {request.path}")
    return render(request, 'errors/403.html', status=403)

def custom_400_view(request, exception):
    logger.warning(f"400 Bad Request: {request.path}")
    return render(request, 'errors/400.html', status=400)
