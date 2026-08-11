from establecimientos.models import Establecimiento
from usuarios.models import RolEstablecimiento

from .auth import es_propietario, usuario_actual


def auth_context(request):
    """Expone el usuario logueado y su nivel de acceso en todas las vistas."""
    usuario = usuario_actual(request)
    return {
        'usuario_actual': usuario,
        'es_propietario': es_propietario(request) if usuario is not None else False,
    }


def establecimientos_globales(request):
    """Expone los establecimientos a los que el usuario tiene acceso y el seleccionado.

    Un propietario ve todos los establecimientos; un operario solo los que le fueron asignados.
    Siempre queda un establecimiento activo: si la sesión aún no tiene uno elegido, se
    selecciona el primero disponible (no existe la vista de "todos los establecimientos").
    """
    usuario = usuario_actual(request)
    todos = list(Establecimiento.objects.filter(activo=True).order_by('nombre'))
    if usuario is not None and not es_propietario(request):
        permitidos = set(
            RolEstablecimiento.objects.filter(usuario=usuario).values_list('establecimiento_id', flat=True)
        )
        establecimientos = [e for e in todos if e.id in permitidos]
    else:
        establecimientos = todos

    establecimiento_id = request.session.get('establecimiento_id')
    establecimiento_actual = None
    if establecimiento_id:
        for establecimiento in establecimientos:
            if establecimiento.id == establecimiento_id:
                establecimiento_actual = establecimiento
                break
    if establecimiento_actual is None and establecimientos and usuario is not None:
        establecimiento_actual = establecimientos[0]
        request.session['establecimiento_id'] = establecimiento_actual.id

    return {
        'establecimientos': establecimientos,
        'establecimiento_actual': establecimiento_actual,
        'establecimiento_actual_id': establecimiento_actual.id if establecimiento_actual else None,
    }
