from urllib.parse import quote

from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse

from usuarios.models import RolEstablecimiento, Usuario

RUTAS_PUBLICAS_PREFIJOS = ('/login', '/recuperar', '/logout')


class RequerirLoginMiddleware:
    """Bloquea el acceso a toda la aplicación salvo a las pantallas públicas de autenticación."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ruta = request.path
        es_publica = (
            ruta.startswith(('/static/', '/media/', '/admin/'))
            or ruta.startswith(RUTAS_PUBLICAS_PREFIJOS)
        )
        es_ajax = (
            ruta.startswith('/api/')
            or request.headers.get('x-requested-with', '').lower() == 'xmlhttprequest'
            or 'application/json' in request.headers.get('accept', '')
        )
        if not es_publica and request.session.get('usuario_id') is None:
            if es_ajax:
                return JsonResponse({'error': 'Debés iniciar sesión para continuar.'}, status=401)
            return HttpResponseRedirect(reverse('login') + '?next=' + quote(request.get_full_path()))
        if not es_publica and request.session.get('usuario_id') is not None:
            # Un usuario desactivado (baja lógica o sin ningún acceso activo) pierde la sesión.
            usuario_id = request.session['usuario_id']
            if Usuario.objects.filter(pk=usuario_id, activo=False).exists():
                request.session.flush()
                if es_ajax:
                    return JsonResponse({'error': 'Tu usuario fue desactivado.'}, status=401)
                return HttpResponseRedirect(reverse('login') + '?next=' + quote(request.get_full_path()))
            filas = RolEstablecimiento.objects.filter(usuario_id=usuario_id)
            if filas.exists() and not filas.filter(estado_acceso=True).exists():
                request.session.flush()
                if es_ajax:
                    return JsonResponse({'error': 'Tu usuario fue desactivado.'}, status=401)
                return HttpResponseRedirect(reverse('login') + '?next=' + quote(request.get_full_path()))
        return self.get_response(request)


class RequerirCambioClaveMiddleware:
    """Mientras el usuario deba reemplazar su clave temporal, solo se le permite
    la pantalla de cambio de clave y cerrar sesión."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ruta = request.path
        usuario_id = request.session.get('usuario_id')
        if (
            usuario_id
            and not ruta.startswith(('/static/', '/media/', '/cambiar_clave', '/logout'))
            and Usuario.objects.filter(pk=usuario_id, debe_cambiar_clave=True).exists()
        ):
            if (
                ruta.startswith('/api/')
                or request.headers.get('x-requested-with', '').lower() == 'xmlhttprequest'
                or 'application/json' in request.headers.get('accept', '')
            ):
                return JsonResponse({'error': 'Debés cambiar tu contraseña temporal antes de continuar.'}, status=403)
            return HttpResponseRedirect(reverse('cambiar_clave'))
        return self.get_response(request)
