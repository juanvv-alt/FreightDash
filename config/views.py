from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import connection
from django.core.cache import cache
import datetime

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
    
    health_status['status'] = 'healthy'
    health_status['timestamp'] = datetime.datetime.now().isoformat()
    return JsonResponse(health_status, status=200)


@require_http_methods(["GET"])
def readiness_check(request):
    """
    Readiness check - returns 200 only when app is ready to serve traffic
    """
    try:
        # Check database connectivity
        connection.ensure_connection()
        
        return JsonResponse({
            'status': 'ready',
            'message': 'Application is ready to serve requests',
            'timestamp': datetime.datetime.now().isoformat()
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
        'timestamp': datetime.datetime.now().isoformat()
    }, status=200)


@require_http_methods(["GET"])
def index(request):
    """
    Simple home page
    """
    return JsonResponse({
        'message': 'FreightDash API is running',
        'environment': 'development',
        'timestamp': datetime.datetime.now().isoformat()
    })
