import logging
from datetime import date, datetime
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.core.validators import validate_email
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from establecimientos.models import Establecimiento
from usuarios.models import Persona, RolEstablecimiento, Usuario

from .auth import (
    ROL_OPERARIO,
    ROL_PROPIETARIO,
    rol_requerido,
    usuario_actual,
    verificar_clave,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

def login_view(request):
    if request.session.get('usuario_id'):
        return redirect('dashboard')
    error = None
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if request.method == 'POST':
        nombre_usuario = request.POST.get('nombre_usuario', '').strip()
        clave = request.POST.get('clave', '')
        usuario = Usuario.objects.select_related('persona').filter(nombre_usuario=nombre_usuario).first()
        if usuario is not None and verificar_clave(usuario, clave):
            if not _usuario_puede_acceder(usuario):
                error = 'Tu usuario está inactivo. Contactate con el propietario.'
            else:
                usuario.fecha_ultimo_acceso = datetime.now()
                usuario.save(update_fields=['fecha_ultimo_acceso'])
                request.session.flush()
                request.session['usuario_id'] = usuario.id
                _establecimiento_por_defecto(request, usuario)
                if usuario.debe_cambiar_clave:
                    return redirect('cambiar_clave')
                if next_url and urlparse(next_url).netloc == '':
                    return redirect(next_url)
                return redirect('dashboard')
        else:
            error = 'Usuario o contraseña incorrectos.'
    return render(request, 'auth/login.html', {'error': error, 'next': next_url})


@require_POST
def logout_view(request):
    request.session.flush()
    return redirect('login')


def cambiar_clave_view(request):
    """Primer ingreso con credenciales temporales: obliga a definir una clave nueva
    y a confirmar/cargar el correo electrónico (necesario para poder recuperarla)."""
    usuario = usuario_actual(request)
    if usuario is None:
        return redirect('login')
    error = None
    correo = ''
    if request.method == 'POST':
        correo = request.POST.get('correo_electronico', '').strip().lower()
        clave = request.POST.get('clave', '')
        clave_confirmacion = request.POST.get('clave_confirmacion', '')
        if not correo:
            error = 'Ingresá tu correo electrónico.'
        else:
            try:
                validate_email(correo)
            except ValidationError:
                error = 'El correo electrónico no es válido.'
            else:
                if usuario.persona.correo_electronico and usuario.persona.correo_electronico.lower() != correo:
                    error = 'El correo no coincide con el registrado para tu usuario.'
        if error is None:
            if not clave or len(clave) < 6:
                error = 'La contraseña debe tener al menos 6 caracteres.'
            elif clave != clave_confirmacion:
                error = 'Las contraseñas no coinciden.'
            elif verificar_clave(usuario, clave):
                error = 'La nueva contraseña no puede ser igual a la anterior.'
        if error is None:
            usuario.persona.correo_electronico = correo
            usuario.persona.save(update_fields=['correo_electronico'])
            usuario.clave = make_password(clave)
            usuario.debe_cambiar_clave = False
            usuario.save(update_fields=['clave', 'debe_cambiar_clave'])
            return redirect('dashboard')
    else:
        correo = (usuario.persona.correo_electronico or '').strip().lower()
    return render(request, 'auth/cambiar_clave.html', {'error': error, 'correo': correo})


def recuperar_view(request):
    enviado = False
    if request.method == 'POST':
        correo = request.POST.get('correo_electronico', '').strip().lower()
        persona = Persona.objects.filter(correo_electronico=correo).first()
        usuario = Usuario.objects.filter(persona=persona).first() if persona else None
        if usuario is not None:
            token = _token_para_usuario(usuario)
            url = _url_absoluta(request, 'restablecer', token)
            try:
                send_mail(
                    'Restablecer contraseña - GanaStock',
                    'Recibimos una solicitud para restablecer tu contraseña.\n\n'
                    f'Hacé clic en el siguiente enlace (válido por 1 hora):\n{url}\n\n'
                    'Si no la pediste, podés ignorar este correo.',
                    settings.DEFAULT_FROM_EMAIL,
                    [correo],
                )
            except Exception as exc:
                logger.error('No se pudo enviar el correo de recuperación a %s: %s', correo, exc)
        # Siempre se muestra el mismo mensaje para no revelar qué cuentas existen.
        enviado = True
    return render(request, 'auth/recuperar.html', {'enviado': enviado})


def restablecer_view(request, token):
    usuario = _usuario_por_token(token)
    if usuario is None:
        return render(request, 'auth/restablecer.html', {'invalido': True})
    if request.method == 'POST':
        clave = request.POST.get('clave', '')
        clave_confirmacion = request.POST.get('clave_confirmacion', '')
        if not clave or len(clave) < 6:
            return render(request, 'auth/restablecer.html', {
                'usuario': usuario.nombre_usuario,
                'error': 'La contraseña debe tener al menos 6 caracteres.',
            })
        if clave != clave_confirmacion:
            return render(request, 'auth/restablecer.html', {
                'usuario': usuario.nombre_usuario,
                'error': 'Las contraseñas no coinciden.',
            })
        usuario.clave = make_password(clave)
        usuario.debe_cambiar_clave = False
        usuario.save(update_fields=['clave', 'debe_cambiar_clave'])
        return redirect('login')
    return render(request, 'auth/restablecer.html', {'usuario': usuario.nombre_usuario})


def _token_para_usuario(usuario):
    """Token firmado sin ':' (se reemplazan por '.') para que el enlace
    no se corte en los clientes de correo al linkificar la URL."""
    return TimestampSigner().sign(str(usuario.pk)).replace(':', '.')


def _url_absoluta(request, nombre_url, token):
    """URL completa del enlace para el correo.

    Usa el host de la petición (así funciona aunque cambie la IP de la PC:
    si pedís la recuperación desde el celular, el enlace apunta a la IP que
    tu celular ya está usando). Solo cuando la petición viene de localhost o
    127.0.0.1 (que el celular no puede abrir) se usa SITE_URL como respaldo."""
    path = reverse(nombre_url, args=[token])
    host = request.get_host()
    host_local = host.split(':')[0].lower() in ('localhost', '127.0.0.1', '::1', '0.0.0.0')
    sitio = getattr(settings, 'SITE_URL', '').rstrip('/')
    if host_local and sitio:
        return f'{sitio}{path}'
    return request.build_absolute_uri(path)


def _usuario_por_token(token):
    try:
        pk = TimestampSigner().unsign(token.replace('.', ':'), max_age=3600)
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None
    return Usuario.objects.filter(pk=pk).first()


def _usuario_puede_acceder(usuario):
    roles = RolEstablecimiento.objects.filter(usuario=usuario)
    if not roles.exists():
        return True
    return roles.filter(estado_acceso=True).exists()


def _establecimiento_por_defecto(request, usuario):
    ids = list(RolEstablecimiento.objects.filter(usuario=usuario).values_list('establecimiento_id', flat=True))
    ids = list(dict.fromkeys(ids))
    if len(ids) == 1:
        request.session['establecimiento_id'] = ids[0]
    else:
        request.session.pop('establecimiento_id', None)


# ---------------------------------------------------------------------------
# Gestión de usuarios (solo propietario)
# ---------------------------------------------------------------------------

def _resolver_establecimiento(request, establecimiento_id):
    if establecimiento_id:
        try:
            return int(establecimiento_id)
        except (TypeError, ValueError):
            return None
    if request.session.get('establecimiento_id'):
        return request.session['establecimiento_id']
    if Establecimiento.objects.count() == 1:
        return Establecimiento.objects.first().id
    return None


def _establecimiento_o_default(request, establecimiento_id):
    establecimiento_id = _resolver_establecimiento(request, establecimiento_id)
    if establecimiento_id is not None:
        return establecimiento_id
    establecimiento = Establecimiento.objects.create(
        nombre='Establecimiento principal',
        fecha_inicio=date.today(),
        ubicacion='Sin especificar',
    )
    return establecimiento.id


def _usuario_data(usuario):
    roles = list(
        RolEstablecimiento.objects.select_related('establecimiento')
        .filter(usuario=usuario)
        .order_by('establecimiento__nombre')
    )
    rol = roles[0] if roles else None
    rol_principal = (
        ROL_PROPIETARIO if any(r.nombre == ROL_PROPIETARIO for r in roles) else ROL_OPERARIO
    )
    estado = 'Activo' if any(r.estado_acceso for r in roles) else 'Inactivo'
    return {
        'id': usuario.id,
        'nombre': usuario.persona.nombre,
        'apellido': usuario.persona.apellido or '',
        'usuario': usuario.nombre_usuario,
        'email': usuario.persona.correo_electronico or '',
        'telefono': usuario.persona.telefono or '',
        'cargo': '',
        'rol': rol_principal,
        'rol_id': rol.id if rol else None,
        'establecimiento_id': rol.establecimiento_id if rol else None,
        'estado': estado,
        'creado': usuario.fecha_creacion.isoformat() if usuario.fecha_creacion else None,
        'acceso': usuario.fecha_ultimo_acceso.isoformat() if usuario.fecha_ultimo_acceso else None,
        'conectado': False,
        'roles': [{
            'id': r.id,
            'establecimiento_id': r.establecimiento_id,
            'establecimiento_nombre': r.establecimiento.nombre,
            'rol': r.nombre,
            'estado_acceso': r.estado_acceso,
            'estado': 'Activo' if r.estado_acceso else 'Inactivo',
            'fecha_ingreso': r.fecha_ingreso.isoformat(),
        } for r in roles],
    }


@rol_requerido(ROL_PROPIETARIO)
@require_http_methods(['GET', 'POST'])
def crear_usuario_api(request):
    if request.method == 'GET':
        usuarios = [_usuario_data(u) for u in Usuario.objects.select_related('persona').order_by('persona__nombre')]
        return JsonResponse({'usuarios': usuarios})
    nombre = request.POST.get('nombre', '').strip()
    apellido = request.POST.get('apellido', '').strip()
    correo = request.POST.get('email', request.POST.get('correo_electronico', '')).strip().lower()
    telefono = request.POST.get('telefono', '').strip()
    nombre_usuario = request.POST.get('usuario', request.POST.get('nombre_usuario', '')).strip()
    clave = request.POST.get('clave', '')
    try:
        if not nombre or not nombre_usuario or not clave:
            raise ValueError('Nombre, usuario y contraseña son obligatorios.')
        if len(clave) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres.')
        if Usuario.objects.filter(nombre_usuario=nombre_usuario).exists():
            raise ValueError('Ese nombre de usuario ya está en uso.')
        if correo and Persona.objects.filter(correo_electronico=correo).exists():
            raise ValueError('Ese correo electrónico ya está registrado.')

        rol = request.POST.get('rol', ROL_OPERARIO).strip()
        if rol not in (ROL_PROPIETARIO, ROL_OPERARIO):
            raise ValueError('Rol no válido.')

        establecimiento_ids = request.POST.getlist('establecimiento_ids')
        if len(establecimiento_ids) == 1 and ',' in establecimiento_ids[0]:
            establecimiento_ids = establecimiento_ids[0].split(',')

        if rol == ROL_PROPIETARIO:
            # El propietario accede automáticamente a todos los establecimientos.
            ids = [e.id for e in Establecimiento.objects.order_by('id')]
        else:
            ids = []
            for est_id in establecimiento_ids:
                resuelto = _resolver_establecimiento(request, est_id)
                if resuelto is not None and resuelto not in ids:
                    ids.append(resuelto)
        if not ids:
            ids = [_establecimiento_o_default(request, None)]

        persona = Persona.objects.create(
            nombre=nombre, apellido=apellido or None,
            correo_electronico=correo or None, telefono=telefono,
        )
        usuario = Usuario.objects.create(
            nombre_usuario=nombre_usuario, clave=make_password(clave),
            persona=persona, debe_cambiar_clave=True,
        )
        for est_id in ids:
            RolEstablecimiento.objects.create(
                usuario=usuario,
                establecimiento_id=est_id,
                nombre=rol,
                fecha_ingreso=date.today(),
                estado_acceso=True,
            )
    except (ValueError, ValidationError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({'usuario': _usuario_data(usuario)}, status=201)


@rol_requerido(ROL_PROPIETARIO)
@require_POST
def actualizar_usuario_api(request, usuario_id):
    """Actualiza clave, rol, establecimientos y acceso de un usuario.

    El rol es a nivel usuario: 'Propietario' accede a todos los establecimientos,
    'Operario' solo a los establecimientos seleccionados. El estado_acceso
    activa/desactiva el acceso del usuario por completo.
    """
    usuario = get_object_or_404(Usuario.objects.select_related('persona'), pk=usuario_id)
    es_el_propio = usuario.id == request.session.get('usuario_id')
    try:
        # Datos personales (nombre, apellido, correo, teléfono).
        persona = usuario.persona
        nombre = request.POST.get('nombre')
        if nombre is not None:
            nombre = nombre.strip()
            if not nombre:
                raise ValueError('El nombre es obligatorio.')
            persona.nombre = nombre
        apellido = request.POST.get('apellido')
        if apellido is not None:
            persona.apellido = apellido.strip() or None
        correo_nuevo = request.POST.get('email', request.POST.get('correo_electronico'))
        if correo_nuevo is not None:
            correo_nuevo = correo_nuevo.strip().lower()
            if correo_nuevo:
                try:
                    validate_email(correo_nuevo)
                except ValidationError:
                    raise ValueError('El correo electrónico no es válido.')
                if Persona.objects.filter(correo_electronico=correo_nuevo).exclude(pk=persona.pk).exists():
                    raise ValueError('Ese correo electrónico ya está registrado.')
            persona.correo_electronico = correo_nuevo or None
        telefono = request.POST.get('telefono')
        if telefono is not None:
            persona.telefono = telefono.strip()
        if any(k in request.POST for k in ('nombre', 'apellido', 'email', 'correo_electronico', 'telefono')):
            persona.save(update_fields=['nombre', 'apellido', 'correo_electronico', 'telefono'])

        nueva_clave = request.POST.get('clave', '')
        if nueva_clave:
            if len(nueva_clave) < 6:
                raise ValueError('La contraseña debe tener al menos 6 caracteres.')
            usuario.clave = make_password(nueva_clave)
            usuario.debe_cambiar_clave = True
            usuario.save(update_fields=['clave', 'debe_cambiar_clave'])

        rol_nuevo = request.POST.get('rol')
        if rol_nuevo:
            rol_nuevo = rol_nuevo.strip()
            if rol_nuevo not in (ROL_PROPIETARIO, ROL_OPERARIO):
                raise ValueError('Rol no válido.')

        estado_param = request.POST.get('estado_acceso')
        nuevo_estado = None
        if estado_param is not None:
            nuevo_estado = estado_param in ('true', 'on', '1', 'Activo')

        establecimiento_ids = request.POST.getlist('establecimiento_ids')
        if len(establecimiento_ids) == 1 and ',' in establecimiento_ids[0]:
            establecimiento_ids = establecimiento_ids[0].split(',')

        filas = RolEstablecimiento.objects.filter(usuario=usuario)
        es_propietario_actual = filas.filter(nombre=ROL_PROPIETARIO).exists()

        if es_el_propio and rol_nuevo and rol_nuevo != ROL_PROPIETARIO:
            raise ValueError('No podés quitarte tu propio rol de propietario.')
        if es_propietario_actual:
            if rol_nuevo and rol_nuevo != ROL_PROPIETARIO:
                _verificar_no_quitar_ultimo_propietario(usuario)
            if nuevo_estado is False:
                _verificar_no_quitar_ultimo_propietario(usuario)

        if rol_nuevo == ROL_PROPIETARIO:
            # El propietario pasa a tener acceso a todos los establecimientos.
            for est in Establecimiento.objects.order_by('id'):
                fila = filas.filter(establecimiento=est).first()
                if fila is None:
                    RolEstablecimiento.objects.create(
                        usuario=usuario, establecimiento=est, nombre=ROL_PROPIETARIO,
                        fecha_ingreso=date.today(), estado_acceso=True,
                    )
                else:
                    fila.nombre = ROL_PROPIETARIO
                    fila.save(update_fields=['nombre'])
        elif rol_nuevo == ROL_OPERARIO or establecimiento_ids:
            # Operario: solo los establecimientos seleccionados.
            elegidos = set()
            for est_id in establecimiento_ids:
                resuelto = _resolver_establecimiento(request, est_id)
                if resuelto is not None:
                    elegidos.add(resuelto)
            if rol_nuevo == ROL_OPERARIO and not elegidos:
                raise ValueError('Seleccioná al menos un establecimiento para un usuario operario.')
            for fila in filas.all():
                if fila.establecimiento_id not in elegidos:
                    fila.delete()
            for est_id in elegidos:
                fila = filas.filter(establecimiento_id=est_id).first()
                if fila is None:
                    RolEstablecimiento.objects.create(
                        usuario=usuario, establecimiento_id=est_id, nombre=ROL_OPERARIO,
                        fecha_ingreso=date.today(), estado_acceso=True,
                    )
                else:
                    fila.nombre = ROL_OPERARIO
                    fila.save(update_fields=['nombre'])

        if nuevo_estado is not None:
            filas.all().update(estado_acceso=nuevo_estado)
    except (ValueError, ValidationError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({'usuario': _usuario_data(usuario)})


def _verificar_no_quitar_ultimo_propietario(usuario):
    """Bloquea quitar/desactivar el acceso si el usuario es el último propietario activo."""
    activos = set(
        RolEstablecimiento.objects.filter(nombre=ROL_PROPIETARIO, estado_acceso=True)
        .values_list('usuario_id', flat=True)
    )
    if usuario.id in activos and len(activos) <= 1:
        raise ValueError('No podés desactivar al último propietario activo.')


@rol_requerido(ROL_PROPIETARIO)
@require_POST
def eliminar_usuario_api(request, usuario_id):
    usuario = get_object_or_404(Usuario, pk=usuario_id)
    if usuario.id == request.session.get('usuario_id'):
        return JsonResponse({'error': 'No podés eliminar tu propio usuario.'}, status=400)
    if _es_ultimo_propietario(usuario):
        return JsonResponse({'error': 'No podés eliminar al último propietario activo.'}, status=400)
    usuario.delete()
    return JsonResponse({'ok': True})


def _es_ultimo_propietario(usuario):
    activos = set(
        RolEstablecimiento.objects.filter(nombre=ROL_PROPIETARIO, estado_acceso=True)
        .values_list('usuario_id', flat=True)
    )
    return usuario.id in activos and len(activos) <= 1
