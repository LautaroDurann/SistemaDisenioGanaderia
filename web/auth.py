from functools import wraps

from django.contrib.auth.hashers import check_password, is_password_usable, make_password
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import resolve_url

from establecimientos.models import Establecimiento
from usuarios.models import RolEstablecimiento, Usuario

ROL_PROPIETARIO = 'Propietario'
ROL_OPERARIO = 'Operario'


def _es_solicitud_ajax(request):
    if request.headers.get('x-requested-with', '').lower() == 'xmlhttprequest':
        return True
    if 'application/json' in request.headers.get('accept', ''):
        return True
    return request.path.startswith('/api/')


def usuario_actual(request):
    """Devuelve el Usuario logueado según la sesión, o None.

    Un usuario dado de baja (activo=False) se considera no logueado.
    """
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None
    return Usuario.objects.select_related('persona').filter(pk=usuario_id, activo=True).first()


def _establecimiento_id_activo(request):
    establecimiento_id = request.session.get('establecimiento_id')
    if establecimiento_id:
        return establecimiento_id
    if Establecimiento.objects.filter(activo=True).count() == 1:
        return Establecimiento.objects.filter(activo=True).first().id
    return None


def rol_usuario(request, usuario=None):
    """Rol del usuario para el establecimiento activo (o el rol más alto si no aplica).

    Devuelve 'Propietario', 'Operario' o None si el usuario no tiene rol asignado.
    """
    usuario = usuario or usuario_actual(request)
    if usuario is None:
        return None
    roles = RolEstablecimiento.objects.filter(usuario=usuario)
    establecimiento_id = _establecimiento_id_activo(request)
    if establecimiento_id:
        rol = roles.filter(establecimiento_id=establecimiento_id).first()
        if rol is not None:
            return rol.nombre
    if roles.filter(nombre=ROL_PROPIETARIO).exists():
        return ROL_PROPIETARIO
    if roles.exists():
        return ROL_OPERARIO
    return None


def es_propietario(request):
    return rol_usuario(request) == ROL_PROPIETARIO


def rol_requerido(*roles_permitidos):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if rol_usuario(request) not in roles_permitidos:
                if _es_solicitud_ajax(request):
                    return JsonResponse({'error': 'No tenés permiso para esta acción.'}, status=403)
                return HttpResponseRedirect(resolve_url('dashboard'))
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def verificar_clave(usuario, clave):
    """Valida la clave soportando hashes y claves legadas en texto plano (que se migran)."""
    if is_password_usable(usuario.clave):
        return check_password(clave, usuario.clave)
    if usuario.clave == clave:
        usuario.clave = make_password(clave)
        usuario.save(update_fields=['clave'])
        return True
    return False
