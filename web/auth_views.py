from datetime import date
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
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
    """Primer ingreso con credenciales temporales: obliga a definir una clave nueva."""
    usuario = usuario_actual(request)
    if usuario is None:
        return redirect('login')
    error = None
    if request.method == 'POST':
        clave = request.POST.get('clave', '')
        clave_confirmacion = request.POST.get('clave_confirmacion', '')
        if not clave or len(clave) < 6:
            error = 'La contraseña debe tener al menos 6 caracteres.'
        elif clave != clave_confirmacion:
            error = 'Las contraseñas no coinciden.'
        elif verificar_clave(usuario, clave):
            error = 'La nueva contraseña no puede ser igual a la anterior.'
        else:
            usuario.clave = make_password(clave)
            usuario.debe_cambiar_clave = False
            usuario.save(update_fields=['clave', 'debe_cambiar_clave'])
            return redirect('dashboard')
    return render(request, 'auth/cambiar_clave.html', {'error': error})


def recuperar_view(request):
    enviado = False
    if request.method == 'POST':
        correo = request.POST.get('correo_electronico', '').strip().lower()
        persona = Persona.objects.filter(correo_electronico=correo).first()
        usuario = Usuario.objects.filter(persona=persona).first() if persona else None
        if usuario is not None:
            token = _token_para_usuario(usuario)
            url = _url_absoluta(request, 'restablecer', token)
            send_mail(
                'Restablecer contraseña - GanaStock',
                'Recibimos una solicitud para restablecer tu contraseña.\n\n'
                f'Hacé clic en el siguiente enlace (válido por 1 hora):\n{url}\n\n'
                'Si no la pediste, podés ignorar este correo.',
                'no-reply@ganastock.com',
                [correo],
                fail_silently=True,
            )
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
    """URL completa del enlace: usa SITE_URL si está configurado, si no el host de la petición."""
    path = reverse(nombre_url, args=[token])
    sitio = getattr(settings, 'SITE_URL', '').rstrip('/')
    if sitio:
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
    return {
        'id': usuario.id,
        'nombre': usuario.persona.nombre,
        'apellido': usuario.persona.apellido or '',
        'usuario': usuario.nombre_usuario,
        'email': usuario.persona.correo_electronico or '',
        'telefono': usuario.persona.telefono or '',
        'cargo': '',
        'rol': rol.nombre if rol else ROL_OPERARIO,
        'rol_id': rol.id if rol else None,
        'establecimiento_id': rol.establecimiento_id if rol else None,
        'estado': 'Activo' if (rol.estado_acceso if rol else True) else 'Inactivo',
        'creado': rol.fecha_ingreso.isoformat() if rol else date.today().isoformat(),
        'acceso': date.today().isoformat() + 'T00:00',
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

        establecimiento_ids = request.POST.getlist('establecimiento_ids')
        roles = request.POST.getlist('roles')
        if len(establecimiento_ids) == 1 and ',' in establecimiento_ids[0]:
            establecimiento_ids = establecimiento_ids[0].split(',')
        if len(roles) == 1 and ',' in roles[0]:
            roles = roles[0].split(',')
        if not establecimiento_ids:
            # Compatibilidad: un solo acceso con los campos clásicos.
            establecimiento_ids = [request.POST.get('establecimiento_id', '')]
            roles = [request.POST.get('rol', ROL_OPERARIO)]
        if len(roles) != len(establecimiento_ids):
            roles = [roles[i] if i < len(roles) else ROL_OPERARIO for i in range(len(establecimiento_ids))]

        persona = Persona.objects.create(
            nombre=nombre, apellido=apellido or None,
            correo_electronico=correo or None, telefono=telefono,
        )
        usuario = Usuario.objects.create(
            nombre_usuario=nombre_usuario, clave=make_password(clave),
            persona=persona, debe_cambiar_clave=True,
        )
        establecimientos_usados = []
        for i, est_id in enumerate(establecimiento_ids):
            rol = roles[i].strip()
            if rol not in (ROL_PROPIETARIO, ROL_OPERARIO):
                rol = ROL_OPERARIO
            resuelto = _resolver_establecimiento(request, est_id)
            if resuelto is None or resuelto in establecimientos_usados:
                continue
            establecimientos_usados.append(resuelto)
            RolEstablecimiento.objects.create(
                usuario=usuario,
                establecimiento_id=resuelto,
                nombre=rol,
                fecha_ingreso=date.today(),
                estado_acceso=True,
            )
        if not establecimientos_usados:
            RolEstablecimiento.objects.create(
                usuario=usuario,
                establecimiento_id=_establecimiento_o_default(request, None),
                nombre=ROL_OPERARIO,
                fecha_ingreso=date.today(),
                estado_acceso=True,
            )
    except (ValueError, ValidationError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({'usuario': _usuario_data(usuario)}, status=201)


@rol_requerido(ROL_PROPIETARIO)
@require_POST
def actualizar_usuario_api(request, usuario_id):
    usuario = get_object_or_404(Usuario.objects.select_related('persona'), pk=usuario_id)
    es_el_propio = usuario.id == request.session.get('usuario_id')
    nueva_clave = request.POST.get('clave', '')
    try:
        if nueva_clave:
            if len(nueva_clave) < 6:
                raise ValueError('La contraseña debe tener al menos 6 caracteres.')
            usuario.clave = make_password(nueva_clave)
            usuario.debe_cambiar_clave = True
            usuario.save(update_fields=['clave', 'debe_cambiar_clave'])

        eliminar_rol_id = request.POST.get('eliminar_rol_establecimiento_id')
        rol_establecimiento_id = request.POST.get('rol_establecimiento_id')
        nuevo_establecimiento_id = request.POST.get('nuevo_establecimiento_id')
        nuevo_rol = request.POST.get('nuevo_rol', ROL_OPERARIO).strip()

        if eliminar_rol_id:
            rol = RolEstablecimiento.objects.filter(pk=eliminar_rol_id, usuario=usuario).first()
            if rol is None:
                raise ValueError('La asignación de rol no existe.')
            if es_el_propio and rol.nombre == ROL_PROPIETARIO:
                raise ValueError('No podés quitarte tu propio rol de propietario.')
            if rol.nombre == ROL_PROPIETARIO and rol.estado_acceso:
                _verificar_no_quitar_ultimo_propietario()
            rol.delete()

        if nuevo_establecimiento_id:
            if nuevo_rol not in (ROL_PROPIETARIO, ROL_OPERARIO):
                raise ValueError('Rol no válido.')
            resuelto = _resolver_establecimiento(request, nuevo_establecimiento_id)
            if resuelto is None:
                raise ValueError('Establecimiento no válido.')
            existente = RolEstablecimiento.objects.filter(usuario=usuario, establecimiento_id=resuelto).first()
            if existente is not None:
                existente.nombre = nuevo_rol
                existente.estado_acceso = True
                existente.save(update_fields=['nombre', 'estado_acceso'])
            else:
                RolEstablecimiento.objects.create(
                    usuario=usuario, establecimiento_id=resuelto, nombre=nuevo_rol,
                    fecha_ingreso=date.today(), estado_acceso=True,
                )

        if rol_establecimiento_id:
            rol = RolEstablecimiento.objects.filter(pk=rol_establecimiento_id, usuario=usuario).first()
            if rol is None:
                raise ValueError('La asignación de rol no existe.')
            era_propietario_activo = rol.nombre == ROL_PROPIETARIO and rol.estado_acceso
            rol_nombre = request.POST.get('rol')
            if rol_nombre:
                if rol_nombre not in (ROL_PROPIETARIO, ROL_OPERARIO):
                    raise ValueError('Rol no válido.')
                if es_el_propio and rol_nombre != ROL_PROPIETARIO:
                    raise ValueError('No podés quitarte tu propio rol de propietario.')
                rol.nombre = rol_nombre
            est_id = request.POST.get('establecimiento_id')
            if est_id:
                rol.establecimiento_id = int(est_id)
            estado = request.POST.get('estado_acceso')
            if estado is not None:
                rol.estado_acceso = estado in ('true', 'on', '1', 'Activo')
            if era_propietario_activo and not (rol.nombre == ROL_PROPIETARIO and rol.estado_acceso):
                _verificar_no_quitar_ultimo_propietario()
            rol.save()
        elif request.POST.get('rol') or request.POST.get('establecimiento_id') or request.POST.get('estado_acceso') is not None:
            # Compatibilidad: se edita la primera asignación del usuario.
            rol = RolEstablecimiento.objects.filter(usuario=usuario).first()
            if rol is None:
                rol = RolEstablecimiento.objects.create(
                    usuario=usuario,
                    establecimiento_id=_establecimiento_o_default(request, request.POST.get('establecimiento_id')),
                    nombre=request.POST.get('rol', ROL_OPERARIO),
                    fecha_ingreso=date.today(),
                    estado_acceso=True,
                )
            era_propietario_activo = rol.nombre == ROL_PROPIETARIO and rol.estado_acceso
            rol_nombre = request.POST.get('rol')
            if rol_nombre:
                if rol_nombre not in (ROL_PROPIETARIO, ROL_OPERARIO):
                    raise ValueError('Rol no válido.')
                if es_el_propio and rol_nombre != ROL_PROPIETARIO:
                    raise ValueError('No podés quitarte tu propio rol de propietario.')
                rol.nombre = rol_nombre
            if request.POST.get('establecimiento_id'):
                rol.establecimiento_id = int(request.POST.get('establecimiento_id'))
            estado = request.POST.get('estado_acceso')
            if estado is not None:
                rol.estado_acceso = estado in ('true', 'on', '1', 'Activo')
            if era_propietario_activo and not (rol.nombre == ROL_PROPIETARIO and rol.estado_acceso):
                _verificar_no_quitar_ultimo_propietario()
            rol.save()
    except (ValueError, ValidationError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({'usuario': _usuario_data(usuario)})


def _verificar_no_quitar_ultimo_propietario():
    """Levanta un error si se intentaría dejar al sistema sin propietarios activos."""
    activos = RolEstablecimiento.objects.filter(nombre=ROL_PROPIETARIO, estado_acceso=True)
    if activos.count() <= 1:
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
    activos = RolEstablecimiento.objects.filter(nombre=ROL_PROPIETARIO, estado_acceso=True)
    if not activos.filter(usuario=usuario).exists():
        return False
    return activos.count() <= 1
