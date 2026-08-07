from establecimientos.models import Establecimiento

from .auth import es_propietario, usuario_actual


def auth_context(request):
    """Expone el usuario logueado y su nivel de acceso en todas las vistas."""
    usuario = usuario_actual(request)
    return {
        'usuario_actual': usuario,
        'es_propietario': es_propietario(request) if usuario is not None else False,
    }


def establecimientos_globales(request):
    """Expone la lista de establecimientos y el seleccionado en todas las vistas."""
    establecimiento_id = request.session.get('establecimiento_id')
    establecimientos = list(Establecimiento.objects.order_by('nombre'))
    establecimiento_actual = None
    if establecimiento_id:
        for establecimiento in establecimientos:
            if establecimiento.id == establecimiento_id:
                establecimiento_actual = establecimiento
                break
    if establecimiento_actual is None and len(establecimientos) == 1:
        establecimiento_actual = establecimientos[0]

    return {
        'establecimientos': establecimientos,
        'establecimiento_actual': establecimiento_actual,
        'establecimiento_actual_id': establecimiento_actual.id if establecimiento_actual else None,
    }
