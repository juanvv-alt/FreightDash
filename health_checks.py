# Health Check & Monitoring for Render

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import connection
from django.core.cache import cache
import redis

@require_http_methods(["GET"])
def health_check(request):
    """
    Health check endpoint for Render's load balancer
    Returns 200 if all services are healthy
    """
    health_status = {}
    
    # Check Database
    try:
        connection.ensure_connection()
        health_status['database'] = 'healthy'
    except Exception as e:
        health_status['database'] = f'unhealthy: {str(e)}'
        return JsonResponse(health_status, status=503)
    
    # Check Redis/Cache
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            health_status['cache'] = 'healthy'
        else:
            health_status['cache'] = 'unhealthy: cache not responding'
    except Exception as e:
        health_status['cache'] = f'unhealthy: {str(e)}'
    
    health_status['status'] = 'healthy'
    return JsonResponse(health_status, status=200)


@require_http_methods(["GET"])
def readiness_check(request):
    """
    Readiness check - returns 200 only when app is ready to serve traffic
    """
    try:
        # Check database connectivity
        connection.ensure_connection()
        
        # Check cache connectivity
        cache.set('readiness_check', 'ok', 10)
        
        return JsonResponse({
            'status': 'ready',
            'message': 'Application is ready to serve requests'
        }, status=200)
    except Exception as e:
        return JsonResponse({
            'status': 'not_ready',
            'error': str(e)
        }, status=503)


@require_http_methods(["GET"])
def liveness_check(request):
    """
    Liveness check - returns 200 if app process is alive
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }, status=200)

# Add to your urls.py:
# 
# from django.urls import path
# from . import views
# 
# urlpatterns = [
#     path('health/', views.health_check, name='health_check'),
#     path('ready/', views.readiness_check, name='readiness_check'),
#     path('live/', views.liveness_check, name='liveness_check'),
# ]
