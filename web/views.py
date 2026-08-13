import calendar
import json
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Sum, Q
from django.db import connection, transaction
from django.http import JsonResponse
from django.db import IntegrityError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Notificacion
from animales.models import Animal, Parto, Preniez
from establecimientos.models import Establecimiento, Parcela
from finanzas.models import Compra, LiquidacionSueldo, MovimientoFinanciero, Venta
from inventario.models import Consumo, DetalleCompra, Insumo, Lote
from sanidad.models import DetalleEvento, EventoSanitario, Enfermedad, Diagnostico
from usuarios.models import Comprador, Proveedor, RolEstablecimiento, Usuario, Veterinario

# Las inseminaciones se registran y muestran solo desde el módulo de Preñez.
TIPO_INSEMINACION = 'Inseminación'
from .auth import ROL_OPERARIO, ROL_PROPIETARIO, es_propietario, rol_requerido, usuario_actual
from .auth_views import _usuario_data


def _categoria(animal):
    """Clasificación exclusiva de bovinos para el filtro de stock."""
    if animal.tipo_animal != 'Bovino':
        return ''

    peso = animal.peso_actual
    if _es_ternero(animal) and peso is not None and peso <= 400:
        return 'Ternero'
    return 'Toro' if animal.sexo == 'Macho' else 'Vaca'


def _es_ternero(animal):
    if not animal.fecha_nacimiento:
        return False
    mes_limite = animal.fecha_nacimiento.month + 6
    anio_limite = animal.fecha_nacimiento.year + (mes_limite - 1) // 12
    mes_limite = (mes_limite - 1) % 12 + 1
    dia_limite = min(animal.fecha_nacimiento.day, calendar.monthrange(anio_limite, mes_limite)[1])
    return date.today() <= date(anio_limite, mes_limite, dia_limite)


def _edad(animal):
    if not animal.fecha_nacimiento:
        return '-'
    meses = (date.today().year - animal.fecha_nacimiento.year) * 12 + date.today().month - animal.fecha_nacimiento.month
    return f'{meses // 12} años' if meses >= 12 else f'{meses} meses'


def _caravana_text(animal):
    return str(animal.id_senasa) if animal.id_senasa is not None else 'Sin caravana'


def _nombre_parcela(parcela):
    if parcela.descripcion:
        return parcela.descripcion.strip()
    return f'Parcela {parcela.id}'


def _parcela_data(parcela, actual=0):
    return {
        'id': parcela.id,
        'nombre': _nombre_parcela(parcela),
        'superficie': round(float(parcela.ancho * parcela.largo) / 10000, 2),
        'ancho': float(parcela.ancho),
        'largo': float(parcela.largo),
        'actual': actual,
        'estado': parcela.estado,
        'fecha': '',
        'responsable': '-',
        'descripcion': parcela.descripcion or '',
    }


def _animal_data(animal):
    estado = 'Vendido' if animal.vendido else ('Muerto' if not animal.vivo else 'Activo')
    return {
        'id': animal.idAnimal, 'idAnimal': animal.idAnimal, 'caravana': _caravana_text(animal), 'nombre': animal.nombre or 'S/N',
        'categoria': _categoria(animal), 'sexo': animal.sexo, 'raza': animal.raza or '-',
        'edad': _edad(animal), 'peso': f"{animal.peso_actual or 0} kg",
        'parcela': str(animal.parcela) if animal.parcela else 'Sin asignar',
        'parcela_id': animal.parcela_id,
        'establecimiento_id': animal.establecimiento_id,
        'establecimiento': str(animal.establecimiento) if animal.establecimiento else '',
        'estado': estado, 'ingreso': animal.fecha_nacimiento.isoformat() if animal.fecha_nacimiento else '-',
        'fecha_muerte': animal.fecha_muerte.isoformat() if animal.fecha_muerte else '',
        'notas': animal.descripcion or '-',
        'tipo_animal': animal.tipo_animal, 'peso_al_nacer': str(animal.peso_al_nacer or ''),
        'peso_al_destete': str(animal.peso_al_destete or ''), 'peso_actual_valor': str(animal.peso_actual or ''),
        'vendido': animal.vendido, 'vivo': animal.vivo, 'enfermo': animal.enfermo, 'castrado': animal.castrado,
        'costo_adquisicion': str(animal.costo_adquisicion or ''), 'precio_venta': str(animal.precio_venta or ''),
        'color': animal.color or '', 'diametro_escrotal': str(animal.diametro_escrotal or ''),
        'madre_id': animal.madre_id, 'madre': str(animal.madre) if animal.madre else 'No registrada',
        'padre_id': animal.padre_id, 'padre': str(animal.padre) if animal.padre else 'No registrado',
        'compra_id': animal.compra_id, 'venta_id': animal.venta_id,
        'compra': str(animal.compra) if animal.compra else 'Sin compra asociada',
        'foto_url': animal.foto.url if animal.foto else '',
        'venta': str(animal.venta) if animal.venta else 'Sin venta asociada',
    }


def _establecimientos_permitidos(request):
    """Todos los establecimientos a los que el usuario accede."""
    usuario = usuario_actual(request)
    if usuario is not None and not _usuario_es_propietario_global(request):
        permitidos_ids = set(
            RolEstablecimiento.objects.filter(usuario=usuario).values_list('establecimiento_id', flat=True)
        )
        return [e for e in Establecimiento.objects.filter(activo=True).order_by('nombre') if e.id in permitidos_ids]
    return list(Establecimiento.objects.filter(activo=True).order_by('nombre'))


def _establecimiento_actual(request):
    """Devuelve el establecimiento activo de la sesión.

    Siempre queda uno seleccionado: si la sesión no tiene ninguno (o el guardado ya
    no es accesible), se elige el primer establecimiento permitido y se lo persiste.
    """
    establecimiento_id = request.session.get('establecimiento_id')
    permitidos = _establecimientos_permitidos(request)

    if establecimiento_id:
        for establecimiento in permitidos:
            if establecimiento.id == establecimiento_id:
                return establecimiento
        request.session.pop('establecimiento_id', None)
    if permitidos:
        establecimiento = permitidos[0]
        request.session['establecimiento_id'] = establecimiento.id
        return establecimiento
    return None


def _usuario_es_propietario_global(request):
    """Un usuario con rol de propietario en algún establecimiento es propietario en todos."""
    usuario = usuario_actual(request)
    if usuario is None:
        return False
    return RolEstablecimiento.objects.filter(usuario=usuario, nombre=ROL_PROPIETARIO).exists()


def _establecimiento_data(establecimiento):
    total_animales = Animal.objects.filter(establecimiento=establecimiento, activo=True).count()
    total_parcelas = Parcela.objects.filter(establecimiento=establecimiento).count()
    return {
        'id': establecimiento.id,
        'nombre': establecimiento.nombre,
        'fecha_inicio': establecimiento.fecha_inicio.isoformat(),
        'ubicacion': establecimiento.ubicacion,
        'total_animales': total_animales,
        'total_parcelas': total_parcelas,
    }


def _animales_de(request):
    """Animales activos del establecimiento activo (o todos si no hay establecimiento seleccionado)."""
    establecimiento = _establecimiento_actual(request)
    qs = Animal.objects.filter(activo=True)
    if establecimiento is not None:
        # El establecimiento se guarda directo en el animal; se contempla el caso
        # de animales históricos que solo lo tienen a través de su parcela.
        qs = qs.filter(Q(establecimiento=establecimiento) | Q(establecimiento__isnull=True, parcela__establecimiento=establecimiento))
    return qs


def _parcelas_de(request):
    establecimiento = _establecimiento_actual(request)
    qs = Parcela.objects.all()
    if establecimiento is not None:
        qs = qs.filter(establecimiento=establecimiento)
    return qs


def _ventas_de(request):
    """Ventas activas cuyo rodeo pertenece al establecimiento activo."""
    qs = Venta.objects.filter(activo=True)
    establecimiento = _establecimiento_actual(request)
    if establecimiento is not None:
        qs = qs.filter(animal__establecimiento=establecimiento).distinct()
    return qs


def _eventos_sanitarios_de(request):
    """Eventos sanitarios activos aplicados a animales del establecimiento activo."""
    qs = EventoSanitario.objects.filter(activo=True)
    establecimiento = _establecimiento_actual(request)
    if establecimiento is not None:
        qs = qs.filter(detalles__animal__establecimiento=establecimiento).distinct()
    return qs


def _page(request, template, data_key=None, data=None):
    # Fuerza la cookie CSRF para que las acciones AJAX de cada pantalla puedan
    # hacer POST sin desactivar la protección de Django.
    get_token(request)
    return render(request, template, {'page_data_key': data_key, 'page_data': data or {}})


def establecimientos_api(request):
    """Lista los establecimientos activos registrados (JSON)."""
    return JsonResponse({'establecimientos': [_establecimiento_data(e) for e in Establecimiento.objects.filter(activo=True).order_by('nombre')]})


@require_POST
def seleccionar_establecimiento(request):
    """Guarda en la sesión el establecimiento activo para filtrar todo el sistema."""
    establecimiento_id = request.POST.get('establecimiento_id')
    if not establecimiento_id or establecimiento_id in ('', 'todos', 'all'):
        return JsonResponse({'error': 'Seleccioná un establecimiento.'}, status=400)
    try:
        establecimiento_id = int(establecimiento_id)
        establecimiento = Establecimiento.objects.get(pk=establecimiento_id, activo=True)
    except (TypeError, ValueError, Establecimiento.DoesNotExist):
        return JsonResponse({'error': 'El establecimiento seleccionado no existe.'}, status=400)
    usuario = usuario_actual(request)
    if usuario is not None and not _usuario_es_propietario_global(request):
        if not RolEstablecimiento.objects.filter(usuario=usuario, establecimiento=establecimiento).exists():
            return JsonResponse({'error': 'No tenés acceso a ese establecimiento.'}, status=403)
    request.session['establecimiento_id'] = establecimiento.id
    return JsonResponse({'ok': True, 'establecimiento_id': establecimiento.id, 'nombre': establecimiento.nombre})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def crear_establecimiento(request):
    """Registra un nuevo establecimiento y lo deja activo en la sesión."""
    try:
        establecimiento = Establecimiento(
            nombre=request.POST['nombre'].strip(),
            fecha_inicio=request.POST['fecha_inicio'],
            ubicacion=request.POST['ubicacion'].strip(),
        )
        establecimiento.full_clean()
        establecimiento.save()
        # Todo propietario accede automáticamente a los establecimientos nuevos.
        for usuario_id, estado in (
            RolEstablecimiento.objects.filter(nombre=ROL_PROPIETARIO)
            .values_list('usuario_id', 'estado_acceso')
            .distinct()
        ):
            RolEstablecimiento.objects.get_or_create(
                usuario_id=usuario_id, establecimiento=establecimiento,
                defaults={
                    'nombre': ROL_PROPIETARIO,
                    'fecha_ingreso': date.today(),
                    'estado_acceso': estado,
                },
            )
    except (KeyError, ValueError, ValidationError):
        return JsonResponse({'error': 'Completá nombre, fecha de inicio y ubicación del establecimiento.'}, status=400)
    request.session['establecimiento_id'] = establecimiento.id
    return JsonResponse({'id': establecimiento.id, 'establecimiento': _establecimiento_data(establecimiento)}, status=201)


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def eliminar_establecimiento(request, establecimiento_id):
    """Da de baja (lógicamente) un establecimiento y lo oculta del sistema."""
    try:
        establecimiento = Establecimiento.objects.get(pk=establecimiento_id, activo=True)
    except (TypeError, ValueError, Establecimiento.DoesNotExist):
        return JsonResponse({'error': 'El establecimiento no existe.'}, status=404)

    if Establecimiento.objects.filter(activo=True).count() <= 1:
        return JsonResponse({'error': 'No se puede dar de baja el único establecimiento del sistema.'}, status=400)

    nombre = establecimiento.nombre
    with transaction.atomic():
        establecimiento.activo = False
        establecimiento.save(update_fields=['activo'])

    if request.session.get('establecimiento_id') == establecimiento_id:
        request.session.pop('establecimiento_id', None)

    return JsonResponse({'ok': True, 'eliminado': nombre})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def eliminar_logo_establecimiento(request):
    """Elimina el logo del establecimiento activo."""
    establecimiento = _establecimiento_actual(request)
    if establecimiento is None:
        return JsonResponse({'error': 'No hay ningún establecimiento activo.'}, status=400)
    if establecimiento.logo:
        establecimiento.logo.delete(save=True)
    return JsonResponse({'ok': True})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def config_establecimiento_api(request):
    """Guarda los datos del establecimiento activo (nombre, ubicación y logo)."""
    establecimiento = _establecimiento_actual(request)
    if establecimiento is None:
        return JsonResponse({'error': 'No hay ningún establecimiento activo para configurar.'}, status=400)

    nombre = request.POST.get('nombre', '').strip()
    ubicacion = request.POST.get('ubicacion', '').strip()
    fecha_inicio = request.POST.get('fecha_inicio', '')
    if not nombre or not ubicacion:
        return JsonResponse({'error': 'Completá el nombre y la ubicación del establecimiento.'}, status=400)

    establecimiento.nombre = nombre
    establecimiento.ubicacion = ubicacion
    if fecha_inicio:
        try:
            establecimiento.fecha_inicio = date.fromisoformat(fecha_inicio)
        except ValueError:
            return JsonResponse({'error': 'La fecha de inicio no es válida.'}, status=400)
    logo = request.FILES.get('logo')
    if logo:
        establecimiento.logo = logo

    try:
        establecimiento.full_clean()
        establecimiento.save()
    except ValidationError as error:
        return JsonResponse({'error': str(error)}, status=400)

    return JsonResponse({
        'ok': True,
        'establecimiento': {
            'id': establecimiento.id,
            'nombre': establecimiento.nombre,
            'fecha_inicio': establecimiento.fecha_inicio.isoformat(),
            'ubicacion': establecimiento.ubicacion,
            'logo': establecimiento.logo.url if establecimiento.logo else '',
        },
    })


PESO_MINIMO_POR_TIPO = {'Bovino': Decimal('180'), 'Ovino': Decimal('25'), 'Porcino': Decimal('60')}


def _es_bajo_peso(animal):
    """Un animal está con bajo peso si perdió peso respecto del destete o si
    no alcanza el peso mínimo de referencia para su especie."""
    if animal.peso_actual is None:
        return False
    if animal.peso_al_destete is not None and animal.peso_actual < animal.peso_al_destete:
        return True
    minimo = PESO_MINIMO_POR_TIPO.get(animal.tipo_animal)
    return minimo is not None and animal.peso_actual < minimo


def _tiempo_estimado(faltan):
    """Formatea un faltante en días como texto legible (ej: '2 semanas y 3 días')."""
    if faltan >= 30:
        return f'{faltan // 30} meses y {(faltan % 30) // 7} semanas'
    semanas, dias = divmod(faltan, 7)
    if semanas and dias:
        return f'{semanas} semanas y {dias} días'
    if semanas:
        return f'{semanas} semanas'
    return f'{dias} días'


def _alertas_dashboard(request, animales=None):
    """Alertas del módulo Dashboard, calculadas con datos reales del establecimiento."""
    if animales is None:
        animales = _animales_de(request)
    establecimiento = _establecimiento_actual(request)
    today = date.today()
    alertas = []

    # Vacunas vencidas: lotes de vacunas con vencimiento pasado y stock pendiente.
    lotes_vacunas = Lote.objects.select_related('insumo').filter(
        activo=True, insumo__activo=True,
        insumo__tipo='Vacuna', fechaVencimiento__lt=today, stockActual__gt=0,
    )
    if establecimiento is not None:
        lotes_vacunas = lotes_vacunas.filter(establecimiento=establecimiento)
    lotes_vacunas = list(lotes_vacunas.order_by('fechaVencimiento', 'id'))
    if lotes_vacunas:
        alertas.append({
            'clave': 'vacunas_vencidas',
            'icono': 'bi-shield-exclamation',
            'color': 'text-bg-danger',
            'titulo': f"{len(lotes_vacunas)} {'vacuna' if len(lotes_vacunas) == 1 else 'vacunas'} vencidas",
            'detalle': ', '.join(l.nombre or f'Lote {l.id}' for l in lotes_vacunas[:5]),
            'url': reverse('insumos'),
        })

    # Próximos partos: preñadas sin parto con fecha estimada dentro de los próximos 30 días.
    prenieces = Preniez.objects.filter(estado_actual='Preñada', parto__isnull=True).select_related('madre')
    if establecimiento is not None:
        prenieces = prenieces.filter(madre__establecimiento=establecimiento)
    faltantes = [(_fecha_estimada_parto(p) - today).days for p in prenieces]
    faltantes = [d for d in faltantes if 0 <= d <= 30]
    if faltantes:
        alertas.append({
            'clave': 'proximos_partos',
            'icono': 'bi-heart-pulse',
            'color': 'text-bg-info',
            'titulo': f"{len(faltantes)} {'parto próximo' if len(faltantes) == 1 else 'partos próximos'}",
            'detalle': f'Estimado en {_tiempo_estimado(min(faltantes))}',
            'url': reverse('prenieces'),
        })

    # Animales enfermos activos.
    enfermos = list(animales.filter(vivo=True, vendido=False, enfermo=True).select_related('parcela'))
    if enfermos:
        parcelas = sorted({_nombre_parcela(a.parcela) for a in enfermos if a.parcela})
        alertas.append({
            'clave': 'animales_enfermos',
            'icono': 'bi-thermometer-half',
            'color': 'text-bg-secondary',
            'titulo': f"{len(enfermos)} {'animal enfermo' if len(enfermos) == 1 else 'animales enfermos'}",
            'detalle': ', '.join(parcelas) or 'Sin parcela asignada',
            'url': reverse('sanidad'),
        })

    # Animales con bajo peso.
    bajo_peso = [a for a in animales.filter(vivo=True, vendido=False).select_related('parcela') if _es_bajo_peso(a)]
    if bajo_peso:
        parcelas = sorted({_nombre_parcela(a.parcela) for a in bajo_peso if a.parcela})
        alertas.append({
            'clave': 'bajo_peso',
            'icono': 'bi-graph-down',
            'color': 'text-bg-dark',
            'titulo': f"{len(bajo_peso)} {'animal con bajo peso' if len(bajo_peso) == 1 else 'animales con bajo peso'}",
            'detalle': ', '.join(parcelas) or 'Sin parcela asignada',
            'url': reverse('stock'),
        })

    # Próximas aplicaciones: eventos sanitarios programados (pendientes) para el futuro.
    eventos_programados = list(_eventos_sanitarios_de(request).filter(
        estado=False, fecha_aplicacion__gte=today,
    ).exclude(tipo=TIPO_INSEMINACION).order_by('fecha_aplicacion'))
    if eventos_programados:
        tipos = sorted({e.tipo for e in eventos_programados})
        proximo_en = _tiempo_estimado((min(e.fecha_aplicacion for e in eventos_programados) - today).days)
        alertas.append({
            'clave': 'proximos_eventos',
            'icono': 'bi-calendar2-event',
            'color': 'text-bg-primary',
            'titulo': f"{len(eventos_programados)} {'evento programado' if len(eventos_programados) == 1 else 'eventos programados'}",
            'detalle': f"{', '.join(tipos)} · próximo en {proximo_en}",
            'url': reverse('sanidad'),
        })

    # Insumos agotados: insumos con lotes cargados pero sin stock restante.
    lotes_qs = Lote.objects.select_related('insumo').filter(activo=True)
    if establecimiento is not None:
        lotes_qs = lotes_qs.filter(establecimiento=establecimiento)
    insumos_por_id = {i.id: i for i in Insumo.objects.filter(activo=True)}
    agotados = []
    for insumo_id, total in (
        lotes_qs.exclude(insumo__isnull=True)
        .values_list('insumo_id')
        .annotate(total=Sum('stockActual'))
        .filter(total=0)
    ):
        if insumo_id in insumos_por_id:
            agotados.append(insumos_por_id[insumo_id])
    if agotados:
        nombres = sorted(a.nombre or f'Insumo {a.id}' for a in agotados)
        alertas.append({
            'clave': 'insumos_agotados',
            'icono': 'bi-box-seam',
            'color': 'text-bg-danger',
            'titulo': f"{len(agotados)} {'insumo agotado' if len(agotados) == 1 else 'insumos agotados'}",
            'detalle': ', '.join(nombres[:5]),
            'url': reverse('insumos'),
        })

    # Compras pendientes de pago.
    compras_pendientes = Compra.objects.filter(estadoDePago='Pendiente').order_by('fecha')
    if establecimiento is not None:
        compras_pendientes = compras_pendientes.filter(mov_financiero__establecimiento=establecimiento)
    compras_pendientes = list(compras_pendientes)
    if compras_pendientes:
        adeudado = sum(c.monto_total for c in compras_pendientes)
        alertas.append({
            'clave': 'compras_pendientes',
            'icono': 'bi-cart-x',
            'color': 'text-bg-warning',
            'titulo': f"{len(compras_pendientes)} {'compra pendiente de pago' if len(compras_pendientes) == 1 else 'compras pendientes de pago'}",
            'detalle': f"Total adeudado: ${adeudado:,.0f}".replace(',', '.'),
            'url': reverse('gastos'),
        })

    # Ventas pendientes de cobro.
    ventas_pendientes = list(_ventas_de(request).filter(estadoDeCobro='Pendiente').order_by('fecha'))
    if ventas_pendientes:
        a_cobrar = sum(v.monto_total for v in ventas_pendientes)
        alertas.append({
            'clave': 'ventas_pendientes',
            'icono': 'bi-cash-coin',
            'color': 'text-bg-success',
            'titulo': f"{len(ventas_pendientes)} {'venta pendiente de cobro' if len(ventas_pendientes) == 1 else 'ventas pendientes de cobro'}",
            'detalle': f"Total a cobrar: ${a_cobrar:,.0f}".replace(',', '.'),
            'url': reverse('ventas'),
        })

    return alertas


def _dashboard_data(request):
    establecimiento = _establecimiento_actual(request)
    today = date.today()

    animales = _animales_de(request)
    animales_activos = animales.filter(vivo=True, vendido=False)
    ventas = _ventas_de(request)

    # Los movimientos financieros son la fuente única de ingresos y gastos reales:
    # se generan automáticamente desde ventas, compras, sueldos y eventos sanitarios.
    movimientos = MovimientoFinanciero.objects.filter(activo=True)
    if establecimiento is not None:
        movimientos = movimientos.filter(establecimiento=establecimiento)

    ventas_mes = ventas.filter(fecha__year=today.year, fecha__month=today.month)
    movimientos_mes = movimientos.filter(fecha__year=today.year, fecha__month=today.month)
    ingresos_mes = movimientos_mes.filter(tipo='Ingreso').aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
    gastos_mes = movimientos_mes.filter(tipo='Egreso').aggregate(total=Sum('monto_total'))['total'] or Decimal('0')

    kpi_total_animales = animales_activos.count()
    kpi_ventas_mes = ventas_mes.count()
    kpi_peso_promedio = animales_activos.aggregate(promedio=Avg('peso_actual'))['promedio'] or Decimal('0')

    # Ganancias y gastos reales de los últimos 12 meses (movimientos financieros)
    meses, ingresos_series, egresos_series = [], [], []
    for i in range(11, -1, -1):
        mes = (today.month - i - 1) % 12 + 1
        anio = today.year + ((today.month - i - 1) // 12)
        meses.append(f'{mes:02d}/{anio}')
        qs = movimientos.filter(fecha__year=anio, fecha__month=mes)
        ingresos_series.append(float(qs.filter(tipo='Ingreso').aggregate(total=Sum('monto_total'))['total'] or 0))
        egresos_series.append(float(qs.filter(tipo='Egreso').aggregate(total=Sum('monto_total'))['total'] or 0))

    # Distribución del rodeo activo por categoría
    distribucion = {}
    for animal in animales_activos:
        categoria = _categoria(animal) or animal.tipo_animal
        distribucion[categoria] = distribucion.get(categoria, 0) + 1

    return {
        'establecimiento_id': establecimiento.id if establecimiento else None,
        'kpis': {
            'total_animales': kpi_total_animales,
            'ventas_mes': kpi_ventas_mes,
            'gastos_mes': float(gastos_mes),
            'peso_promedio': round(float(kpi_peso_promedio), 2),
            'ingresos_mes': float(ingresos_mes),
        },
        'chart': {
            'labels_json': json.dumps(meses),
            'ingresos_json': json.dumps(ingresos_series),
            'egresos_json': json.dumps(egresos_series),
        },
        'distribucion': distribucion,
        'alertas': _alertas_dashboard(request, animales),
    }


def inicio(request):
    """Página de bienvenida pública del establecimiento.

    Si el usuario ya inició sesión, se lo envía directo al panel para no
    interponer la landing entre el login y el sistema."""
    if request.session.get('usuario_id'):
        return redirect('dashboard')
    galeria_dir = os.path.join(settings.BASE_DIR, 'static', 'assets', 'img', 'fotosInicio')
    fotos = []
    if os.path.isdir(galeria_dir):
        fotos = sorted(
            f for f in os.listdir(galeria_dir)
            if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        )
    usadas_arriba = {'Establecimiento.jpg', 'Campo.jpg', 'Duenios.jpg'}
    fotos_galeria = [f for f in fotos if f not in usadas_arriba]
    return render(request, 'inicio.html', {'fotos_galeria': fotos_galeria})


def dashboard(request):
    return _page(request, 'index.html', 'dashboard', _dashboard_data(request))


def dashboard_api(request):
    return JsonResponse(_dashboard_data(request))


def _notificaciones_visibles(request):
    """Notificaciones activas del usuario en el establecimiento actual."""
    usuario = usuario_actual(request)
    if usuario is None:
        return Notificacion.objects.none()
    qs = Notificacion.objects.filter(usuario=usuario, activa=True, eliminada=False)
    establecimiento = _establecimiento_actual(request)
    if establecimiento is not None:
        qs = qs.filter(establecimiento=establecimiento)
    else:
        qs = qs.filter(establecimiento__isnull=True)
    return qs


def _notificacion_data(notificacion):
    return {
        'id': notificacion.id,
        'clave': notificacion.clave,
        'titulo': notificacion.titulo,
        'detalle': notificacion.detalle,
        'icono': notificacion.icono,
        'color': notificacion.color,
        'url': notificacion.url,
        'leida': notificacion.leida,
        'creada': notificacion.creada.strftime('%d/%m/%Y %H:%M'),
    }


def _sincronizar_notificaciones(request, alertas):
    """Persiste las alertas calculadas como notificaciones por usuario/establecimiento.

    Las notificaciones eliminadas no se vuelven a mostrar aunque la alerta siga
    presente; el estado "leída" se conserva entre actualizaciones.
    """
    usuario = usuario_actual(request)
    if usuario is None:
        return
    establecimiento = _establecimiento_actual(request)

    claves_activas = set()
    for alerta in alertas:
        clave = alerta['clave']
        claves_activas.add(clave)
        try:
            notificacion = Notificacion.objects.get(
                usuario=usuario, establecimiento=establecimiento, clave=clave,
            )
        except Notificacion.DoesNotExist:
            notificacion = Notificacion(
                usuario=usuario, establecimiento=establecimiento, clave=clave,
            )
        if notificacion.eliminada:
            continue
        notificacion.titulo = alerta['titulo']
        notificacion.detalle = alerta['detalle']
        notificacion.icono = alerta['icono']
        notificacion.color = alerta['color']
        notificacion.url = alerta['url']
        notificacion.activa = True
        notificacion.save()

    _notificaciones_visibles(request).exclude(clave__in=claves_activas).update(activa=False)


def notificaciones_api(request):
    """Lista las notificaciones activas y el total sin leer."""
    alertas = _alertas_dashboard(request)
    _sincronizar_notificaciones(request, alertas)
    notificaciones = _notificaciones_visibles(request).order_by('leida', '-creada')
    return JsonResponse({
        'notificaciones': [_notificacion_data(n) for n in notificaciones],
        'no_leidas': notificaciones.filter(leida=False).count(),
    })


@require_POST
def marcar_notificacion_leida(request, notificacion_id):
    """Marca una notificación como leída (se dispara al hacer clic en ella)."""
    notificacion = get_object_or_404(Notificacion, pk=notificacion_id, usuario=usuario_actual(request))
    notificacion.leida = True
    notificacion.save(update_fields=['leida'])
    return JsonResponse({'ok': True, 'no_leidas': _notificaciones_visibles(request).filter(leida=False).count()})


@require_POST
def marcar_todas_notificaciones_leidas(request):
    _notificaciones_visibles(request).update(leida=True)
    return JsonResponse({'ok': True, 'no_leidas': 0})


@require_POST
def eliminar_notificacion(request, notificacion_id):
    notificacion = get_object_or_404(Notificacion, pk=notificacion_id, usuario=usuario_actual(request))
    notificacion.eliminada = True
    notificacion.save(update_fields=['eliminada'])
    return JsonResponse({'ok': True, 'no_leidas': _notificaciones_visibles(request).filter(leida=False).count()})


@require_POST
def eliminar_todas_notificaciones(request):
    _notificaciones_visibles(request).update(eliminada=True)
    return JsonResponse({'ok': True, 'no_leidas': 0})


def stock(request):
    animales = _animales_de(request).select_related('parcela', 'madre', 'padre', 'compra', 'venta')
    establecimiento = _establecimiento_actual(request)
    permitidos = _establecimientos_permitidos(request)
    return _page(request, 'stock.html', 'stock', {
        'animales': [_animal_data(a) for a in animales],
        'establecimientos': [{'id': e.id, 'nombre': str(e)} for e in permitidos],
        'parcelas': [
            {'id': p.id, 'nombre': str(p), 'establecimiento_id': p.establecimiento_id}
            for p in Parcela.objects.filter(establecimiento_id__in=[e.id for e in permitidos]).select_related('establecimiento')
        ],
        'progenitores': [
            {'id': a.idAnimal, 'nombre': f'#{a.id_senasa if a.id_senasa is not None else "S/C"} — {a.nombre or "S/N"}', 'sexo': a.sexo, 'tipo_animal': a.tipo_animal}
            for a in animales
        ],
        # Madres para el filtro de stock: todas las hembras del establecimiento
        # activo que tienen crías registradas, sin importar su estado.
        'madres': [
            {'id': a.idAnimal, 'nombre': f'#{a.id_senasa if a.id_senasa is not None else "S/C"} — {a.nombre or "S/N"}'}
            for a in animales.filter(sexo='Hembra', hijos__isnull=False).distinct()
        ],
        'establecimiento_id': establecimiento.id if establecimiento else None,
    })


def _to_iso_date(value):
    if value is None:
        return ''
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _normalizar_dni(valor):
    """Devuelve None cuando el DNI viene vacío para permitir personas sin DNI.
    Si se ingresa, debe tener entre 7 y 8 caracteres."""
    valor = (valor or '').strip()
    if valor and not (7 <= len(valor) <= 8):
        raise ValueError('El DNI debe tener entre 7 y 8 caracteres.')
    return valor or None


def _venta_data(venta):
    animales = list(venta.animal_set.all())
    establecimiento = next((a.establecimiento for a in animales if a.establecimiento_id is not None), None)
    return {
        'id': venta.id, 'tipo': venta.tipo, 'fecha': _to_iso_date(venta.fecha),
        'peso_total': str(venta.peso_total), 'porcentaje_desbaste': str((venta.porcentajeDesbaste or Decimal('0')).quantize(Decimal('0.01'))),
        'peso_desbastado': str(venta.peso_desbastado),
        'precio_por_kg': str(venta.precio_por_kg),
        'monto_total': str(venta.monto_total), 'detalle': venta.detalle or '',
        'estado_de_cobro': venta.estadoDeCobro or 'Pendiente',
        'metodo_de_pago': venta.metodoDePago or 'Efectivo',
        'comprador_id': venta.comprador_id,
        'comprador': str(venta.comprador) if venta.comprador else 'Sin comprador',
        'establecimiento_id': establecimiento.id if establecimiento else None,
        'establecimiento': establecimiento.nombre if establecimiento else '',
        'animales': [_animal_data(a) for a in animales],
    }


def _comprador_data(comprador):
    return {
        'id': comprador.id,
        'nombre': comprador.nombre,
        'apellido': comprador.apellido,
        'dni': comprador.dni,
        'correo': comprador.correo_electronico,
        'telefono': comprador.telefono or '',
        'fecha_nacimiento': _to_iso_date(comprador.fecha_nacimiento),
    }


def _proveedor_data(proveedor):
    return {
        'id': proveedor.id,
        'nombre': proveedor.nombre,
        'apellido': proveedor.apellido,
        'dni': proveedor.dni,
        'correo': proveedor.correo_electronico,
        'telefono': proveedor.telefono or '',
        'fecha_nacimiento': _to_iso_date(proveedor.fecha_nacimiento),
    }


def _compra_data(compra):
    lote = compra.detalles.select_related('lote__insumo').first()
    detalle_insumo = None
    if lote is not None and lote.lote is not None:
        detalle_insumo = {
            'lote_id': lote.lote_id,
            'lote_nombre': lote.lote.nombre or f'Lote {lote.lote.id}',
            'insumo_id': lote.lote.insumo_id,
            'insumo_nombre': lote.lote.insumo.nombre if lote.lote.insumo else '',
            'insumo_tipo': lote.lote.insumo.tipo if lote.lote.insumo else '',
            'cantidad': str(lote.cantidad or 0),
            'precio_unitario': str(lote.precioUnitario or 0),
            'fecha_vencimiento': _to_iso_date(lote.lote.fechaVencimiento),
        }
    animal = compra.animal_set.first()
    detalle_animal = None
    if animal is not None:
        detalle_animal = {
            'animal_id': animal.idAnimal,
            'caravana': _caravana_text(animal),
            'nombre': animal.nombre or '',
            'tipo_animal': animal.tipo_animal,
            'sexo': animal.sexo,
            'raza': animal.raza or '',
            'color': animal.color or '',
            'fecha_nacimiento': _to_iso_date(animal.fecha_nacimiento),
            'peso_al_nacer': str(animal.peso_al_nacer or ''),
            'peso_actual': str(animal.peso_actual or ''),
            'diametro_escrotal': str(animal.diametro_escrotal or ''),
            'detalle': animal.descripcion or '',
        }
    return {
        'id': compra.id, 'tipo': compra.tipo, 'fecha': _to_iso_date(compra.fecha),
        'monto_total': str(compra.monto_total), 'detalle': compra.detalle or '',
        'estado_de_pago': compra.estadoDePago or 'Pendiente',
        'metodo_de_pago': compra.metodoDePago or 'Efectivo',
        'proveedor_id': compra.proveedor_id,
        'proveedor': str(compra.proveedor) if compra.proveedor else 'Sin proveedor',
        'establecimiento_id': compra.mov_financiero.establecimiento_id if compra.mov_financiero_id else None,
        'establecimiento': compra.mov_financiero.establecimiento.nombre if compra.mov_financiero_id and compra.mov_financiero.establecimiento else '',
        'lote': detalle_insumo,
        'animal': detalle_animal,
    }


def _movimientos_financieros_data(request=None):
    movimientos = MovimientoFinanciero.objects.filter(activo=True).order_by('-fecha', '-id')
    establecimiento = _establecimiento_actual(request) if request is not None else None
    if establecimiento is not None:
        movimientos = movimientos.filter(establecimiento=establecimiento)
    return [{
        'id': m.id, 'fecha': m.fecha.isoformat(), 'tipo': m.tipo, 'nombre': m.nombre,
        'detalle': m.detalle or '', 'monto_total': str(m.monto_total),
        'establecimiento_id': m.establecimiento_id,
        'establecimiento': m.establecimiento.nombre if m.establecimiento else '',
    } for m in movimientos]


@rol_requerido(ROL_PROPIETARIO)
def finanzas(request):
    # Pantalla central de Finanzas: métricas, gráfico y listado CRUD de movimientos financieros.
    # Los movimientos se muestran según el establecimiento activo en la sesión.
    today = date.today()
    anio = today.year
    mes = today.month

    establecimiento = _establecimiento_actual(request)
    movimientos_qs = MovimientoFinanciero.objects.filter(activo=True)
    if establecimiento is not None:
        movimientos_qs = movimientos_qs.filter(establecimiento=establecimiento)

    movimientos_mes = movimientos_qs.filter(fecha__year=anio, fecha__month=mes)
    kpi_total = movimientos_mes.count()
    kpi_ingresos = movimientos_mes.filter(tipo='Ingreso').aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
    kpi_egresos = movimientos_mes.filter(tipo='Egreso').aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
    kpi_balance = kpi_ingresos - kpi_egresos

    # Datos mensuales para gráfico (últimos 6 meses)
    meses = []
    ingresos_series = []
    egresos_series = []
    for i in range(5, -1, -1):
        m = (today.month - i - 1) % 12 + 1
        y = today.year + ((today.month - i - 1) // 12)
        meses.append(f"{y}-{m:02d}")
        qs = movimientos_qs.filter(fecha__year=y, fecha__month=m)
        ingresos_series.append(float(qs.filter(tipo='Ingreso').aggregate(total=Sum('monto_total'))['total'] or 0))
        egresos_series.append(float(qs.filter(tipo='Egreso').aggregate(total=Sum('monto_total'))['total'] or 0))

    # 1) Flujo de caja acumulado del año (mes a mes)
    netos_por_mes = {}
    for m in movimientos_qs.filter(fecha__year=anio):
        netos_por_mes[m.fecha.month] = netos_por_mes.get(m.fecha.month, Decimal('0')) + (
            m.monto_total if m.tipo == 'Ingreso' else -m.monto_total
        )
    flujo_etiquetas = []
    flujo_valores = []
    saldo = Decimal('0')
    for mes_num in range(1, 13):
        saldo += netos_por_mes.get(mes_num, Decimal('0'))
        flujo_etiquetas.append(MESES_NOMBRE[mes_num][:3])
        flujo_valores.append(float(saldo))

    # 2) Egresos por categoría (año actual), clasificando el origen de cada egreso
    mov_egresos_anio = movimientos_qs.filter(tipo='Egreso', fecha__year=anio)
    compra_tipo_por_mov = {
        c.mov_financiero_id: c.tipo
        for c in Compra.objects.filter(activo=True, mov_financiero_id__in=mov_egresos_anio.values('id'))
    }
    evento_mov_ids = set(
        EventoSanitario.objects.filter(mov_financiero_id__in=mov_egresos_anio.values('id'))
        .values_list('mov_financiero_id', flat=True)
    )
    liquidacion_mov_ids = set(
        LiquidacionSueldo.objects.filter(movimiento_financiero_id__in=mov_egresos_anio.values('id'))
        .values_list('movimiento_financiero_id', flat=True)
    )
    categorias = {}
    for m in mov_egresos_anio:
        categoria = (compra_tipo_por_mov.get(m.id)
                     or ('Sanidad' if m.id in evento_mov_ids else None)
                     or ('Sueldos' if m.id in liquidacion_mov_ids else 'Gastos varios'))
        categorias[categoria] = categorias.get(categoria, Decimal('0')) + m.monto_total
    categorias_ordenadas = sorted(categorias.items(), key=lambda par: par[1], reverse=True)
    categorias_etiquetas = [c for c, _ in categorias_ordenadas]
    categorias_valores = [float(v) for _, v in categorias_ordenadas]

    # 3) Comparativa entre establecimientos (año actual)
    establecimientos = _establecimientos_permitidos(request)
    establecimientos_etiquetas = []
    establecimientos_ingresos = []
    establecimientos_egresos = []
    for e in establecimientos:
        qs_e = MovimientoFinanciero.objects.filter(establecimiento=e, activo=True, fecha__year=anio)
        establecimientos_etiquetas.append(e.nombre)
        establecimientos_ingresos.append(float(
            qs_e.filter(tipo='Ingreso').aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
        ))
        establecimientos_egresos.append(float(
            qs_e.filter(tipo='Egreso').aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
        ))

    return _page(request, 'finanzas.html', 'finanzas', {
        'kpis': {
            'total_movimientos_mes': kpi_total,
            'ingresos_mes': float(kpi_ingresos),
            'egresos_mes': float(kpi_egresos),
            'balance_mes': float(kpi_balance),
        },
        'movimientos': _movimientos_financieros_data(request)[:50],
        'chart': {
            'labels_json': json.dumps(meses),
            'ingresos_json': json.dumps(ingresos_series),
            'egresos_json': json.dumps(egresos_series),
        },
        'flujo': {
            'etiquetas_json': json.dumps(flujo_etiquetas),
            'valores_json': json.dumps(flujo_valores),
        },
        'categorias': {
            'etiquetas_json': json.dumps(categorias_etiquetas),
            'valores_json': json.dumps(categorias_valores),
        },
        'establecimientos': {
            'etiquetas_json': json.dumps(establecimientos_etiquetas),
            'ingresos_json': json.dumps(establecimientos_ingresos),
            'egresos_json': json.dumps(establecimientos_egresos),
        },
    })


def _parse_decimal(value):
    return Decimal(str(value)) if value is not None and str(value).strip() != '' else None


@rol_requerido(ROL_PROPIETARIO)
def finanzas_api_list_create(request):
    """GET: lista movimientos (JSON). POST: crear movimiento financiero."""
    if request.method == 'GET':
        return JsonResponse({'movimientos': _movimientos_financieros_data(request)})

    if request.method == 'POST':
        try:
            fecha = request.POST.get('fecha')
            tipo = request.POST.get('tipo')
            nombre = request.POST.get('nombre')
            detalle = request.POST.get('detalle')
            monto = request.POST.get('monto_total')
            if not fecha or not tipo or not nombre or not monto:
                return JsonResponse({'error': 'Faltan campos obligatorios.'}, status=400)
            movimiento = MovimientoFinanciero.objects.create(
                fecha=date.fromisoformat(fecha), tipo=tipo, nombre=nombre, detalle=detalle or '',
                monto_total=_parse_decimal(monto),
                establecimiento=_establecimiento_actual(request),
            )
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
        return JsonResponse({'movimiento': {
            'id': movimiento.id, 'fecha': movimiento.fecha.isoformat(), 'tipo': movimiento.tipo,
            'nombre': movimiento.nombre, 'detalle': movimiento.detalle or '', 'monto_total': str(movimiento.monto_total),
            'establecimiento_id': movimiento.establecimiento_id,
            'establecimiento': movimiento.establecimiento.nombre if movimiento.establecimiento else '',
        }}, status=201)


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def actualizar_movimiento_financiero(request, movimiento_id):
    try:
        movimiento = get_object_or_404(MovimientoFinanciero.objects.select_for_update(), pk=movimiento_id)
        fecha = request.POST.get('fecha')
        if fecha:
            movimiento.fecha = date.fromisoformat(fecha)
        movimiento.tipo = request.POST.get('tipo') or movimiento.tipo
        movimiento.nombre = request.POST.get('nombre') or movimiento.nombre
        detalle = request.POST.get('detalle')
        if detalle:
            movimiento.detalle = detalle
        monto = request.POST.get('monto_total')
        if monto:
            movimiento.monto_total = _parse_decimal(monto)
            _sincronizar_costo_entidades(movimiento)
        movimiento.save()
    except (ValueError, ValidationError, IntegrityError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'movimiento': {
        'id': movimiento.id, 'fecha': movimiento.fecha.isoformat(), 'tipo': movimiento.tipo,
        'nombre': movimiento.nombre, 'detalle': movimiento.detalle or '', 'monto_total': str(movimiento.monto_total),
        'establecimiento_id': movimiento.establecimiento_id,
        'establecimiento': movimiento.establecimiento.nombre if movimiento.establecimiento else '',
    }})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def eliminar_movimiento_financiero(request, movimiento_id):
    movimiento = get_object_or_404(MovimientoFinanciero, pk=movimiento_id, activo=True)
    if (Venta.objects.filter(activo=True, mov_financiero_id=movimiento.id).exists()
            or Compra.objects.filter(activo=True, mov_financiero_id=movimiento.id).exists()
            or EventoSanitario.objects.filter(activo=True, mov_financiero_id=movimiento.id).exists()
            or LiquidacionSueldo.objects.filter(movimiento_financiero_id=movimiento.id).exists()):
        return JsonResponse({
            'error': 'Este movimiento está vinculado a una venta, compra, evento sanitario o liquidación de sueldo. '
                     'Eliminalo desde el módulo correspondiente para mantener la coherencia del sistema.'
        }, status=400)
    movimiento.activo = False
    movimiento.save(update_fields=['activo'])
    return JsonResponse({'ok': True})


def _sincronizar_costo_entidades(movimiento):
    """Mantiene el costo del movimiento sincronizado con la entidad asociada
    (venta, compra, evento sanitario o liquidación de sueldo)."""
    monto = movimiento.monto_total
    Venta.objects.filter(mov_financiero_id=movimiento.id).update(monto_total=monto)
    Compra.objects.filter(mov_financiero_id=movimiento.id).update(monto_total=monto)
    EventoSanitario.objects.filter(mov_financiero_id=movimiento.id).update(costo_total=monto)
    LiquidacionSueldo.objects.filter(movimiento_financiero_id=movimiento.id).update(sueldo=monto)


@rol_requerido(ROL_PROPIETARIO)
def ventas(request):
    animales = _animales_de(request).filter(vivo=True, vendido=False).select_related('parcela')
    ventas_registradas = _ventas_de(request).select_related('comprador').prefetch_related('animal_set').order_by('-fecha', '-id')
    today = date.today()
    total_ventas = ventas_registradas.count()
    ganancia_total = ventas_registradas.aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
    # Resumen del año activo (calendario).
    ventas_anio = ventas_registradas.filter(fecha__year=today.year).count()
    ingresos_anio = ventas_registradas.filter(fecha__year=today.year).aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
    # peso_desbastado es una propiedad (se calcula), por eso se suma en Python.
    kilos_anio = sum((v.peso_desbastado for v in ventas_registradas.filter(fecha__year=today.year)), Decimal('0'))
    compradores = list(Comprador.objects.filter(activo=True).order_by('apellido', 'nombre'))
    # Promedio de ingresos por mes: ingresos del año actual divididos entre los meses
    # transcurridos desde enero hasta el mes actual.
    promedio_por_mes = (ingresos_anio / today.month) if ingresos_anio else Decimal('0')
    chart_years = [today.year - i for i in range(4, -1, -1)]
    chart_labels = [str(year) for year in chart_years]
    chart_series = []
    for year in chart_years:
        total = ventas_registradas.filter(fecha__year=year).aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
        chart_series.append(float(total))

    return _page(request, 'ventas.html', 'ventas', {
        'animales': [_animal_data(a) for a in animales],
        'ventas': [_venta_data(v) for v in ventas_registradas],
        'compradores': [_comprador_data(c) for c in compradores],
        'summary': {
            'total_ventas': total_ventas,
            'ganancia_total': float(ganancia_total),
            'promedio_por_mes': float(promedio_por_mes),
            'ventas_anio': ventas_anio,
            'ingresos_anio': float(ingresos_anio),
            'kilos_anio': float(kilos_anio),
            'compradores': len(compradores),
        },
        'chart': {
            'labels_json': json.dumps(chart_labels),
            'series_json': json.dumps(chart_series),
        },
    })


@rol_requerido(ROL_PROPIETARIO)
def gastos(request):
    """Módulo de Gastos: compras del negocio y liquidación de sueldos de empleados."""
    establecimiento = _establecimiento_actual(request)

    compras_registradas = Compra.objects.filter(activo=True).select_related('proveedor').prefetch_related(
        'detalles__lote__insumo', 'animal_set'
    ).order_by('-fecha', '-id')
    liquidaciones = LiquidacionSueldo.objects.select_related(
        'empleado__persona', 'establecimiento'
    ).order_by('-fecha', '-idLiquidacion')

    if establecimiento is not None:
        compras_registradas = compras_registradas.filter(mov_financiero__establecimiento=establecimiento)
        liquidaciones = liquidaciones.filter(establecimiento=establecimiento)

    today = date.today()
    total_compras = compras_registradas.count()
    compras_total = compras_registradas.aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
    compras_anio = compras_registradas.filter(fecha__year=today.year).aggregate(total=Sum('monto_total'))['total'] or Decimal('0')

    total_liquidaciones = liquidaciones.count()
    sueldos_total = liquidaciones.aggregate(total=Sum('sueldo'))['total'] or Decimal('0')
    sueldos_anio = liquidaciones.filter(fecha__year=today.year).aggregate(total=Sum('sueldo'))['total'] or Decimal('0')

    # Otros egresos: movimientos financieros de egreso sin entidad asociada
    # (no provienen de compras, ventas, eventos sanitarios ni liquidaciones).
    vinculados = set(
        Compra.objects.filter(activo=True, mov_financiero_id__isnull=False).values_list('mov_financiero_id', flat=True)
    ) | set(
        Venta.objects.filter(activo=True, mov_financiero_id__isnull=False).values_list('mov_financiero_id', flat=True)
    ) | set(
        EventoSanitario.objects.filter(activo=True, mov_financiero_id__isnull=False).values_list('mov_financiero_id', flat=True)
    ) | set(
        LiquidacionSueldo.objects.filter(movimiento_financiero_id__isnull=False)
        .values_list('movimiento_financiero_id', flat=True)
    )
    otros_qs = MovimientoFinanciero.objects.filter(activo=True, tipo='Egreso').exclude(id__in=vinculados)
    if establecimiento is not None:
        otros_qs = otros_qs.filter(establecimiento=establecimiento)
    otros_qs = otros_qs.order_by('-fecha', '-id')

    total_otros = otros_qs.count()
    otros_total = otros_qs.aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
    otros_anio = otros_qs.filter(fecha__year=today.year).aggregate(total=Sum('monto_total'))['total'] or Decimal('0')

    proveedores = list(Proveedor.objects.filter(activo=True).order_by('apellido', 'nombre'))
    insumos = list(Insumo.objects.filter(activo=True).order_by('tipo', 'nombre'))
    empleados = _empleados_de(request)

    # Los pagos de sueldos y otros egresos se suman a las compras: todos son egresos del módulo.
    chart_years = [today.year - i for i in range(4, -1, -1)]
    chart_labels = [str(year) for year in chart_years]
    chart_series_compras = []
    chart_series_sueldos = []
    chart_series_otros = []
    for year in chart_years:
        total_c = compras_registradas.filter(fecha__year=year).aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
        total_s = liquidaciones.filter(fecha__year=year).aggregate(total=Sum('sueldo'))['total'] or Decimal('0')
        total_o = otros_qs.filter(fecha__year=year).aggregate(total=Sum('monto_total'))['total'] or Decimal('0')
        chart_series_compras.append(float(total_c))
        chart_series_sueldos.append(float(total_s))
        chart_series_otros.append(float(total_o))

    return _page(request, 'gastos.html', 'gastos', {
        'compras': [_compra_data(c) for c in compras_registradas],
        'proveedores': [_proveedor_data(p) for p in proveedores],
        'insumos': [_insumo_data(i) for i in insumos],
        'liquidaciones': [_liquidacion_data(l) for l in liquidaciones],
        'empleados': [_empleado_data(e) for e in empleados],
        'otros': [{
            'id': m.id, 'fecha': m.fecha.isoformat(), 'tipo': m.tipo, 'nombre': m.nombre,
            'detalle': m.detalle or '', 'monto_total': str(m.monto_total),
            'establecimiento_id': m.establecimiento_id,
            'establecimiento': m.establecimiento.nombre if m.establecimiento else '',
        } for m in otros_qs],
        'summary': {
            'total_compras': total_compras,
            'total_liquidaciones': total_liquidaciones,
            'total_otros': total_otros,
            'total_gastos': total_compras + total_liquidaciones + total_otros,
            'egresos_total': float(compras_total + sueldos_total + otros_total),
            'egresos_anio_actual': float(compras_anio + sueldos_anio + otros_anio),
            'total_sueldos': float(sueldos_total),
            'sueldos_anio_actual': float(sueldos_anio),
            'otros_total': float(otros_total),
            'proveedores': len(proveedores),
            'empleados': len(empleados),
        },
        'chart_gastos': {
            'labels_json': json.dumps(chart_labels),
            'compras_json': json.dumps(chart_series_compras),
            'sueldos_json': json.dumps(chart_series_sueldos),
            'otros_json': json.dumps(chart_series_otros),
        },
        'chart_sueldos': {
            'labels_json': json.dumps(chart_labels),
            'series_json': json.dumps(chart_series_sueldos),
        },
    })


def parcelas(request):
    parcelas = _parcelas_de(request).select_related('establecimiento').prefetch_related('animal_set')
    datos, animales = [], {}
    for p in parcelas:
        nombre = _nombre_parcela(p)
        residentes = [_animal_data(a) for a in p.animal_set.filter(vivo=True, vendido=False)]
        animales[nombre] = residentes
        datos.append(_parcela_data(p, actual=len(residentes)))
    establecimiento = _establecimiento_actual(request)
    return _page(request, 'parcelas.html', 'parcelas', {
        'parcelas': datos,
        'animales_por_parcela': animales,
        'establecimiento_id': establecimiento.id if establecimiento else None,
    })


def _lote_data(lote):
    return {
        'id': lote.id,
        'nombre': lote.nombre or f'Lote {lote.id}',
        'insumo_id': lote.insumo_id,
        'insumo': str(lote.insumo) if lote.insumo else '-',
        'insumo_nombre': lote.insumo.nombre if lote.insumo else '-',
        'insumo_tipo': lote.insumo.tipo if lote.insumo else '',
        'stock': str(lote.stockActual or 0),
        'fecha_vencimiento': lote.fechaVencimiento.isoformat() if lote.fechaVencimiento else '',
        'establecimiento_id': lote.establecimiento_id,
        'establecimiento': lote.establecimiento.nombre if lote.establecimiento else '',
    }


def _insumo_data(insumo):
    return {
        'id': insumo.id,
        'nombre': insumo.nombre or f'Insumo {insumo.id}',
        'tipo': insumo.tipo or '',
        'unidad_de_medida': insumo.unidadDeMedida or '',
    }


def _asignar_evento_sanitario(evento, datos):
    tipo = datos.get('tipo', '').strip()
    fecha_aplicacion = datos.get('fecha_aplicacion', '').strip()
    animal_ids = [int(value) for value in datos.getlist('animales') if str(value).strip()]
    if not animal_ids:
        animal_ids = [int(value) for value in datos.getlist('animal_ids') if str(value).strip()]
    if not animal_ids:
        animal_ids = [int(value) for value in datos.getlist('animal_id') if str(value).strip()]
    if not animal_ids:
        animal_id = datos.get('animal_id', '').strip()
        if animal_id:
            animal_ids = [int(animal_id)]

    if not tipo or not fecha_aplicacion or not animal_ids:
        raise ValueError('Tipo, fecha y al menos un animal son obligatorios para el evento sanitario.')
    if len(animal_ids) != len(set(animal_ids)):
        raise ValueError('No se permiten animales duplicados en el mismo evento.')

    evento.tipo = tipo
    evento.fecha_aplicacion = fecha_aplicacion
    evento.estado = datos.get('estado', 'true') in ('true', 'on', '1')
    evento.costo_total = _parse_decimal(datos.get('costo_total'))
    evento.cantidad = _parse_decimal(datos.get('cantidad'))
    evento.detalle = datos.get('detalle', '').strip() or None
    evento.veterinario_id = int(datos['veterinario_id']) if datos.get('veterinario_id') else None
    evento.diagnostico_id = int(datos['diagnostico_id']) if datos.get('diagnostico_id') else None
    evento.lote_id = int(datos['lote_id']) if datos.get('lote_id') else None
    evento.padre_id = int(datos['padre_id']) if datos.get('padre_id') else None
    evento.padre_donante = datos.get('padre_donante', '').strip() or None
    return animal_ids


def _evento_sanitario_data(evento):
    detalles = []
    for detalle in evento.detalles.all():
        animal = detalle.animal
        detalles.append({
            'id': animal.idAnimal,
            'nombre': animal.nombre or 'S/N',
            'caravana': str(animal.id_senasa) if animal.id_senasa is not None else 'S/N',
            'tipo_animal': animal.tipo_animal,
            'categoria': _categoria(animal),
            'edad': _edad(animal),
            'parcela': str(animal.parcela) if animal.parcela else 'Sin asignar',
            'activo': animal.activo,
            'cantidad_dosis': str(detalle.cantidad_dosis or ''),
        })

    caravana = ', '.join(f"#{d['caravana']}" for d in detalles) if detalles else 'S/N'
    animales_text = ', '.join(d['nombre'] for d in detalles) if detalles else 'S/N'
    categorias = ', '.join(sorted({d['categoria'] for d in detalles if d['categoria']})) if detalles else ''

    return {
        'id': evento.id,
        'detalle': evento.detalle or '',
        'tipo': evento.tipo,
        'fecha_aplicacion': evento.fecha_aplicacion.isoformat(),
        'estado': evento.estado,
        'costo_total': str(evento.costo_total or 0),
        'mov_financiero_id': evento.mov_financiero_id,
        'animal_ids': [d['id'] for d in detalles],
        'animales': detalles,
        'animal': animales_text,
        'caravana': caravana,
        'categoria': categorias,
        'edad': detalles[0]['edad'] if detalles else '-',
        'parcela': detalles[0]['parcela'] if detalles else 'Sin asignar',
        'veterinario_id': evento.veterinario_id,
        'veterinario': str(evento.veterinario) if evento.veterinario else '-',
        'diagnostico_id': evento.diagnostico_id,
        'diagnostico': str(evento.diagnostico) if evento.diagnostico else '-',
        'lote_id': evento.lote_id if hasattr(evento, 'lote_id') else None,
        'lote': str(evento.lote) if hasattr(evento, 'lote') and evento.lote else '-',
        'lote_insumo_id': evento.lote.insumo_id if evento.lote and evento.lote.insumo_id else None,
        'lote_insumo_tipo': evento.lote.insumo.tipo if evento.lote and evento.lote.insumo else None,
        'cantidad': str(getattr(evento, 'cantidad', '') or ''),
        'padre_id': evento.padre_id,
        'padre': str(evento.padre) if evento.padre_id else '-',
    }


def _enfermedad_data(enfermedad):
    return {
        'id': enfermedad.id,
        'nombre': enfermedad.nombre,
        'es_zoonotica': enfermedad.es_zoonotica,
        'descripcion': enfermedad.descripcion or '',
    }


def _diagnostico_data(diagnostico):
    return {
        'id': diagnostico.id,
        'fecha_deteccion': diagnostico.fecha_deteccion.isoformat(),
        'estado_actual': diagnostico.estado_actual,
        'observaciones': diagnostico.observaciones or '',
        'animal_id': diagnostico.animal_id,
        'animal': diagnostico.animal.nombre or 'S/N',
        'caravana': str(diagnostico.animal.id_senasa) if diagnostico.animal.id_senasa is not None else 'S/N',
        'enfermedad_id': diagnostico.enfermedad_id,
        'enfermedad': diagnostico.enfermedad.nombre,
    }


def _veterinario_data(veterinario):
    return {
        'id': veterinario.id,
        'nombre': veterinario.nombre,
        'apellido': veterinario.apellido,
        'dni': veterinario.dni,
        'correo_electronico': veterinario.correo_electronico,
        'telefono': veterinario.telefono or '',
        'fecha_nacimiento': veterinario.fecha_nacimiento.isoformat() if veterinario.fecha_nacimiento else '',
        'nombre_completo': str(veterinario),
    }


def _asignar_enfermedad(enfermedad, datos):
    enfermedad.nombre = datos['nombre'].strip()
    enfermedad.es_zoonotica = datos.get('es_zoonotica') in ('true', 'on', '1', 'True')
    enfermedad.descripcion = datos.get('descripcion', '').strip()


def _asignar_diagnostico(diagnostico, datos):
    diagnostico.animal_id = int(datos['animal_id'])
    diagnostico.enfermedad_id = int(datos['enfermedad_id'])
    diagnostico.fecha_deteccion = datos['fecha_deteccion']
    diagnostico.estado_actual = datos.get('estado_actual', 'En tratamiento')
    diagnostico.observaciones = datos.get('observaciones', '').strip()


def _asignar_veterinario(veterinario, datos):
    veterinario.dni = _normalizar_dni(datos.get('dni', ''))
    veterinario.nombre = datos['nombre'].strip()
    veterinario.apellido = datos.get('apellido', '').strip() or None
    veterinario.correo_electronico = datos.get('correo_electronico', '').strip() or None
    veterinario.telefono = datos.get('telefono', '').strip()
    veterinario.fecha_nacimiento = datos.get('fecha_nacimiento') or None


def crear_enfermedad(request):
    try:
        enfermedad = Enfermedad()
        _asignar_enfermedad(enfermedad, request.POST)
        enfermedad.full_clean()
        enfermedad.save()
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'enfermedad': _enfermedad_data(enfermedad)}, status=201)


@require_POST
def actualizar_enfermedad(request, enfermedad_id):
    enfermedad = get_object_or_404(Enfermedad, pk=enfermedad_id)
    try:
        _asignar_enfermedad(enfermedad, request.POST)
        enfermedad.full_clean()
        enfermedad.save()
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'enfermedad': _enfermedad_data(enfermedad)})


@require_POST
def eliminar_enfermedad(request, enfermedad_id):
    enfermedad = get_object_or_404(Enfermedad, pk=enfermedad_id)
    enfermedad.delete()
    return JsonResponse({'ok': True})


@require_POST
def crear_diagnostico(request):
    try:
        diagnostico = Diagnostico()
        _asignar_diagnostico(diagnostico, request.POST)
        diagnostico.full_clean()
        diagnostico.save()
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    _recalcular_estado_enfermo(diagnostico.animal)
    return JsonResponse({'diagnostico': _diagnostico_data(diagnostico)}, status=201)


@require_POST
def actualizar_diagnostico(request, diagnostico_id):
    diagnostico = get_object_or_404(Diagnostico, pk=diagnostico_id)
    animal_anterior = diagnostico.animal
    try:
        _asignar_diagnostico(diagnostico, request.POST)
        diagnostico.full_clean()
        diagnostico.save()
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    _recalcular_estado_enfermo(animal_anterior)
    if diagnostico.animal_id != animal_anterior.idAnimal:
        _recalcular_estado_enfermo(diagnostico.animal)
    return JsonResponse({'diagnostico': _diagnostico_data(diagnostico)})


@require_POST
def eliminar_diagnostico(request, diagnostico_id):
    diagnostico = get_object_or_404(Diagnostico, pk=diagnostico_id)
    animal = diagnostico.animal
    diagnostico.delete()
    _recalcular_estado_enfermo(animal)
    return JsonResponse({'ok': True})


@require_POST
def crear_veterinario(request):
    try:
        veterinario = Veterinario()
        _asignar_veterinario(veterinario, request.POST)
        veterinario.full_clean()
        veterinario.save()
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'veterinario': _veterinario_data(veterinario)}, status=201)


@require_POST
def actualizar_veterinario(request, veterinario_id):
    veterinario = get_object_or_404(Veterinario, pk=veterinario_id, activo=True)
    try:
        _asignar_veterinario(veterinario, request.POST)
        veterinario.full_clean()
        veterinario.save()
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'veterinario': _veterinario_data(veterinario)})


@require_POST
def eliminar_veterinario(request, veterinario_id):
    veterinario = get_object_or_404(Veterinario, pk=veterinario_id, activo=True)
    veterinario.activo = False
    veterinario.save(update_fields=['activo'])
    return JsonResponse({'ok': True})


def _recalcular_estado_enfermo(animal):
    animal.enfermo = Diagnostico.objects.filter(animal=animal).exclude(estado_actual='Curado').exists()
    animal.save(update_fields=['enfermo'])


def sanidad(request):
    today = date.today()
    establecimiento = _establecimiento_actual(request)
    # Las inseminaciones se registran desde el módulo de Preñez; no se muestran ni se registran en Sanidad.
    eventos = _eventos_sanitarios_de(request).exclude(tipo=TIPO_INSEMINACION) \
        .select_related('veterinario', 'diagnostico', 'lote').prefetch_related('detalles__animal__parcela') \
        .order_by('-fecha_aplicacion', '-id')
    eventos_aplicados_mes = eventos.filter(
        estado=True,
        fecha_aplicacion__year=today.year, fecha_aplicacion__month=today.month,
    ).count()
    proximas_aplicaciones = eventos.filter(
        estado=False, fecha_aplicacion__gte=today,
    ).count()
    animales = _animales_de(request).filter(vivo=True).select_related('parcela').order_by('id_senasa')
    animales_enfermos = animales.filter(enfermo=True).count()
    enfermedades = Enfermedad.objects.order_by('nombre')
    diagnosticos = Diagnostico.objects.select_related('animal', 'enfermedad').order_by('-fecha_deteccion')
    if establecimiento is not None:
        diagnosticos = diagnosticos.filter(animal__establecimiento=establecimiento)
    veterinarios = Veterinario.objects.filter(activo=True).order_by('apellido', 'nombre')
    lotes = Lote.objects.filter(activo=True, insumo__activo=True).select_related('insumo').order_by('insumo__nombre', 'fechaVencimiento')
    if establecimiento is not None:
        lotes = lotes.filter(establecimiento=establecimiento)
    # Incluir animales vivos aunque ya hayan sido vendidos para permitir registrar eventos y diagnósticos históricos.

    data = {
        'kpis': {
            'eventos_aplicados_mes': eventos_aplicados_mes,
            'aplicaciones_mes': eventos_aplicados_mes,
            'proximas_aplicaciones': proximas_aplicaciones,
            'veterinarios': veterinarios.count(),
            'eventos_totales': eventos.count(),
        },
        'eventos': [_evento_sanitario_data(e) for e in eventos],
        'enfermedades': [_enfermedad_data(e) for e in enfermedades],
        'diagnosticos': [_diagnostico_data(d) for d in diagnosticos],
        'veterinarios': [_veterinario_data(v) for v in veterinarios],
        'lotes': [_lote_data(l) for l in lotes],
        'insumos': [_insumo_data(i) for i in Insumo.objects.filter(activo=True).order_by('nombre')],
        'tipos_evento': [choice[0] for choice in EventoSanitario.TIPO_CHOICES if choice[0] != TIPO_INSEMINACION],
        'animales': [{
            'id': a.idAnimal,
            'nombre': a.nombre or 'S/N',
            'caravana': str(a.id_senasa) if a.id_senasa is not None else 'S/N',
            'sexo': a.sexo,
            'tipo_animal': a.tipo_animal,
            'categoria': _categoria(a),
            'parcela': str(a.parcela) if a.parcela else 'Sin asignar',
            'enfermo': a.enfermo,
        } for a in animales],
    }
    return _page(request, 'sanidad.html', 'sanidad', data)


def _sync_detalles(evento, animal_ids):
    """Sincroniza los DetalleEvento del evento con la lista de animales recibida.

    Solo agrega los animales nuevos y elimina los que ya no están; los detalles
    existentes se conservan (no se revalidan ni se pierde la dosis cargada)."""
    actuales = set(evento.detalles.values_list('animal_id', flat=True))
    nuevos = set(animal_ids)
    evento.detalles.exclude(animal_id__in=nuevos).delete()
    for animal_id in nuevos - actuales:
        DetalleEvento.objects.create(evento=evento, animal_id=animal_id)


@require_POST
def crear_evento_sanitario(request):
    if request.POST.get('tipo') == TIPO_INSEMINACION:
        return JsonResponse({'error': 'Las inseminaciones se registran desde el módulo de Preñez.'}, status=400)
    try:
        evento = EventoSanitario()
        animal_ids = _asignar_evento_sanitario(evento, request.POST)
        evento.full_clean()
        with transaction.atomic():
            evento.save()
            _sync_detalles(evento, animal_ids)
            _sync_movimiento_evento(evento, _establecimiento_actual(request))
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'evento': _evento_sanitario_data(evento)}, status=201)


@require_POST
def actualizar_evento_sanitario(request, evento_id):
    evento = get_object_or_404(EventoSanitario, pk=evento_id)
    if evento.tipo == TIPO_INSEMINACION or request.POST.get('tipo') == TIPO_INSEMINACION:
        return JsonResponse({'error': 'Las inseminaciones se gestionan desde el módulo de Preñez.'}, status=400)
    try:
        animal_ids = _asignar_evento_sanitario(evento, request.POST)
        evento.full_clean()
        with transaction.atomic():
            evento.save()
            _sync_detalles(evento, animal_ids)
            _sync_movimiento_evento(evento, _establecimiento_actual(request))
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'evento': _evento_sanitario_data(evento)})


def _sync_movimiento_evento(evento, establecimiento=None):
    """Registra en Finanzas el gasto del evento cuando está Aplicado y tiene costo, o lo elimina si ya no corresponde."""
    costo = evento.costo_total or Decimal('0')
    if evento.estado and costo > 0:
        movimiento, _ = MovimientoFinanciero.objects.update_or_create(
            pk=evento.mov_financiero_id,
            defaults={
                'tipo': 'Egreso',
                'nombre': f'Evento sanitario #{evento.id}',
                'monto_total': costo,
                'fecha': evento.fecha_aplicacion,
                'detalle': evento.detalle or f'Gasto de {evento.tipo} registrado desde el módulo de Sanidad.',
                'establecimiento': establecimiento,
                'activo': True,
            },
        )
        if evento.mov_financiero_id != movimiento.id:
            EventoSanitario.objects.filter(pk=evento.pk).update(mov_financiero=movimiento)
    elif evento.mov_financiero_id:
        MovimientoFinanciero.objects.filter(pk=evento.mov_financiero_id, activo=True).update(activo=False)
        EventoSanitario.objects.filter(pk=evento.pk).update(mov_financiero=None)


@require_POST
def eliminar_evento_sanitario(request, evento_id):
    """Da de baja (lógicamente) un evento sanitario y su movimiento financiero asociado."""
    evento = get_object_or_404(EventoSanitario, pk=evento_id, activo=True)
    if evento.tipo == TIPO_INSEMINACION:
        return JsonResponse({'error': 'Las inseminaciones se gestionan desde el módulo de Preñez.'}, status=400)
    movimiento_id = evento.mov_financiero_id
    with transaction.atomic():
        evento.activo = False
        evento.save(update_fields=['activo'])
        if movimiento_id:
            MovimientoFinanciero.objects.filter(pk=movimiento_id, activo=True).update(activo=False)
    return JsonResponse({'ok': True})


def vacunacion(request):
    return sanidad(request)


@rol_requerido(ROL_PROPIETARIO, ROL_OPERARIO)
def usuarios(request):
    actual = usuario_actual(request)
    es_propietario_user = es_propietario(request)
    if es_propietario_user:
        usuarios_data = [_usuario_data(u) for u in Usuario.objects.filter(activo=True).select_related('persona')]
    else:
        # Un operario solo puede ver (y editar) su propia información.
        usuarios_data = [_usuario_data(actual)] if actual else []
    data = {'usuarios': usuarios_data,
            'establecimientos_data': [{'id': e.id, 'nombre': e.nombre} for e in Establecimiento.objects.filter(activo=True).order_by('nombre')],
            'usuario_actual_id': actual.id if actual else None,
            'es_propietario': es_propietario_user}
    return _page(request, 'usuarios.html', 'usuarios', data)


# ---------------------------------------------------------------------------
# Módulo de Configuración: base de datos, respaldos y restauración
# ---------------------------------------------------------------------------

def _directorio_respaldos():
    """Carpeta donde se guardan las copias de seguridad de la base de datos."""
    directorio = settings.BASE_DIR / 'backups'
    directorio.mkdir(parents=True, exist_ok=True)
    return directorio


def _tamano_legible(cantidad):
    """Formatea un tamaño en bytes como texto legible (ej: '1,2 MB')."""
    if cantidad is None:
        return '—'
    for unidad in ('B', 'KB', 'MB', 'GB'):
        if cantidad < 1024:
            return f'{cantidad:.0f} {unidad}' if unidad == 'B' else f'{cantidad:.1f} {unidad}'
        cantidad /= 1024
    return f'{cantidad:.2f} TB'


def _motor_base_de_datos():
    """Devuelve el nombre del motor real de la base de datos y su tamaño."""
    motor = settings.DATABASES['default']['ENGINE']
    if motor.endswith('sqlite3'):
        nombre_archivo = connection.settings_dict.get('NAME')
        tamano = '—'
        if nombre_archivo and 'memory' not in str(nombre_archivo):
            try:
                tamano = _tamano_legible(os.path.getsize(nombre_archivo))
            except OSError:
                tamano = '—'
        return f'SQLite {sqlite3.sqlite_version}', tamano
    if motor.endswith('postgresql'):
        version = '—'
        try:
            with connection.cursor() as cursor:
                cursor.execute('SHOW server_version')
                version = cursor.fetchone()[0]
        except Exception:
            version = '—'
        return f'PostgreSQL {version}', '—'
    return motor.rsplit('.', 1)[-1], '—'


def _listar_respaldos():
    """Lista las copias de seguridad guardadas, de la más reciente a la más antigua."""
    respaldos = []
    archivos = sorted(
        _directorio_respaldos().glob('*.sqlite3'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for archivo in archivos:
        try:
            stats = archivo.stat()
        except OSError:
            continue
        respaldos.append({
            'nombre': archivo.name,
            'fecha': datetime.fromtimestamp(stats.st_mtime).strftime('%d/%m/%Y %H:%M'),
            'tamano': _tamano_legible(stats.st_size),
        })
    return respaldos


def _validar_nombre_respaldo(nombre):
    """Valida que el nombre corresponda a un archivo dentro de la carpeta de respaldos."""
    nombre = os.path.basename(nombre or '')
    if not nombre.endswith('.sqlite3'):
        raise ValueError('El respaldo indicado no es válido.')
    ruta = (_directorio_respaldos() / nombre).resolve()
    if _directorio_respaldos().resolve() not in ruta.parents:
        raise ValueError('El respaldo indicado no es válido.')
    if not ruta.is_file():
        raise FileNotFoundError('El respaldo indicado no existe.')
    return ruta


@rol_requerido(ROL_PROPIETARIO)
def respaldos_api(request):
    """Información real de la base de datos y listado de respaldos (JSON)."""
    motor, tamano = _motor_base_de_datos()
    respaldos = _listar_respaldos()
    return JsonResponse({
        'info': {
            'motor': motor,
            'tamano': tamano,
            'ultimo_respaldo': respaldos[0]['fecha'] if respaldos else None,
            'estado': 'Operativo',
        },
        'respaldos': respaldos,
    })


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def crear_respaldo_db(request):
    """Genera una copia de seguridad de la base de datos (SQLite)."""
    if not settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
        return JsonResponse({'error': 'El respaldo solo está disponible con una base de datos SQLite.'}, status=400)
    nombre = f'respaldo_{datetime.now().strftime("%Y%m%d_%H%M%S")}.sqlite3'
    ruta = _directorio_respaldos() / nombre
    try:
        connection.ensure_connection()
        destino = sqlite3.connect(str(ruta))
        try:
            connection.connection.backup(destino)
        finally:
            destino.close()
    except Exception as error:
        return JsonResponse({'error': f'No se pudo crear el respaldo: {error}'}, status=500)
    stats = ruta.stat()
    return JsonResponse({'ok': True, 'respaldo': {
        'nombre': ruta.name,
        'fecha': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'tamano': _tamano_legible(stats.st_size),
    }}, status=201)


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def restaurar_respaldo_db(request):
    """Restaura una copia de seguridad, reemplazando los datos actuales."""
    if not settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
        return JsonResponse({'error': 'La restauración solo está disponible con una base de datos SQLite.'}, status=400)
    try:
        ruta = _validar_nombre_respaldo(request.POST.get('respaldo'))
    except (ValueError, FileNotFoundError) as error:
        return JsonResponse({'error': str(error)}, status=404 if isinstance(error, FileNotFoundError) else 400)
    try:
        connection.ensure_connection()
        # Se copia el respaldo directamente sobre la conexión activa de Django, de
        # modo que las siguientes consultas ya ven los datos restaurados.
        origen = sqlite3.connect(str(ruta))
        try:
            with origen:
                origen.backup(connection.connection)
        finally:
            origen.close()
    except Exception as error:
        return JsonResponse({'error': f'No se pudo restaurar el respaldo: {error}'}, status=500)
    return JsonResponse({'ok': True, 'restaurado': ruta.name})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def eliminar_respaldo_db(request):
    """Elimina una copia de seguridad guardada."""
    try:
        ruta = _validar_nombre_respaldo(request.POST.get('respaldo'))
    except (ValueError, FileNotFoundError) as error:
        return JsonResponse({'error': str(error)}, status=404 if isinstance(error, FileNotFoundError) else 400)
    try:
        ruta.unlink()
    except OSError as error:
        return JsonResponse({'error': f'No se pudo eliminar el respaldo: {error}'}, status=500)
    return JsonResponse({'ok': True, 'eliminado': ruta.name})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def optimizar_base_datos(request):
    """Optimiza la base de datos SQLite (PRAGMA optimize + VACUUM)."""
    if not settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
        return JsonResponse({'error': 'La optimización solo está disponible con una base de datos SQLite.'}, status=400)
    try:
        connection.ensure_connection()
        conexion = connection.connection
        conexion.execute('PRAGMA optimize')
        conexion.execute('VACUUM')
    except Exception as error:
        return JsonResponse({'error': f'No se pudo optimizar la base de datos: {error}'}, status=500)
    return JsonResponse({'ok': True})


@rol_requerido(ROL_PROPIETARIO)
def configuracion(request):
    motor, tamano = _motor_base_de_datos()
    respaldos = _listar_respaldos()
    return _page(request, 'configuracion.html', None, {
        'info_base_de_datos': {
            'motor': motor,
            'tamano': tamano,
            'ultimo_respaldo': respaldos[0]['fecha'] if respaldos else None,
            'estado': 'Operativo',
        },
        'respaldos': respaldos,
    })


@rol_requerido(ROL_PROPIETARIO)
def establecimiento(request):
    """Módulo del establecimiento activo: logo, nombre, ubicación y fecha de inicio."""
    return _page(request, 'establecimiento.html', None, {})


def stock_api(request):
    return JsonResponse({'animales': [_animal_data(a) for a in _animales_de(request).select_related('parcela', 'madre', 'padre', 'compra', 'venta')]})


def _validar_parcela_del_establecimiento(request, parcela_id, establecimiento_id=None):
    """Rechaza parcelas que no pertenezcan al establecimiento asignado al animal."""
    if not parcela_id or not establecimiento_id:
        return
    if not Parcela.objects.filter(pk=parcela_id, establecimiento_id=establecimiento_id).exists():
        raise ValueError('La parcela seleccionada no pertenece al establecimiento indicado.')


def _validar_establecimiento_accesible(request, establecimiento_id):
    """Rechaza asignar el animal a un establecimiento al que el usuario no accede."""
    if not establecimiento_id or _usuario_es_propietario_global(request):
        return
    usuario = usuario_actual(request)
    if usuario is not None and not RolEstablecimiento.objects.filter(
        usuario=usuario, establecimiento_id=establecimiento_id,
    ).exists():
        raise ValueError('No tenés acceso a ese establecimiento.')


def _asignar_campos_animal(animal, datos, es_alta=False):
    """Centraliza la asignación para que el alta y la edición tengan las mismas reglas."""
    valor_senasa = datos.get('id_senasa', '').strip()
    if valor_senasa:
        # Caravana SENASA alfanumérica: solo letras y números, sin símbolos.
        if not re.fullmatch(r'[A-Za-z0-9]+', valor_senasa):
            raise ValueError('La caravana SENASA solo puede contener letras y números.')
    animal.id_senasa = valor_senasa or None
    animal.nombre = datos.get('nombre', '').strip()
    animal.tipo_animal = datos['tipo_animal']
    animal.sexo = datos['sexo']
    raza = datos.get('raza', '').strip() or None
    if raza and not raza[0].isalpha():
        raise ValueError('La raza debe comenzar con una letra.')
    animal.raza = raza
    fecha_nacimiento = datos.get('fecha_nacimiento') or None
    if fecha_nacimiento:
        try:
            fecha_nacimiento = date.fromisoformat(fecha_nacimiento)
        except ValueError:
            raise ValueError('La fecha de nacimiento no es válida.')
    animal.fecha_nacimiento = fecha_nacimiento
    for campo in ('peso_al_nacer', 'peso_al_destete', 'peso_actual'):
        setattr(animal, campo, datos.get(campo) or None)
    # El costo de adquisición y el precio de venta se cargan desde los módulos
    # de compras y ventas; el alta/edición de animales no los modifica.
    for campo in ('costo_adquisicion', 'precio_venta'):
        if campo in datos:
            setattr(animal, campo, datos.get(campo) or None)
    # El diámetro escrotal solo se toca si el formulario lo envía (módulo de Stock).
    # Al registrar una compra no se pide, así se conserva el valor cargado en Animales.
    if 'diametro_escrotal' in datos:
        animal.diametro_escrotal = datos.get('diametro_escrotal') or None
    animal.vendido = datos.get('vendido') == 'on'
    animal.vivo = datos.get('vivo') == 'on' if 'vivo' in datos else es_alta
    animal.enfermo = datos.get('enfermo') == 'on'
    animal.castrado = datos.get('castrado') == 'on'
    # Fecha de muerte: solo tiene sentido para animales no vivos. Si el animal
    # vuelve a estar vivo se limpia; si está muerto y no se envía fecha se
    # conserva la cargada previamente.
    if animal.vivo:
        animal.fecha_muerte = None
    else:
        valor_muerte = datos.get('fecha_muerte', '').strip()
        if valor_muerte:
            try:
                fecha_muerte = date.fromisoformat(valor_muerte)
            except ValueError:
                raise ValueError('La fecha de muerte no es válida.')
            if animal.fecha_nacimiento and fecha_muerte < animal.fecha_nacimiento:
                raise ValueError('La fecha de muerte no puede ser anterior a la fecha de nacimiento.')
            animal.fecha_muerte = fecha_muerte
    animal.color = datos.get('color', '').strip() or None
    parcela_id = datos.get('parcela_id') or None
    animal.parcela_id = parcela_id
    # El establecimiento se asigna directo; si no se envía, se deduce de la parcela.
    establecimiento_id = datos.get('establecimiento_id') or None
    if not establecimiento_id and parcela_id:
        parcela = Parcela.objects.filter(pk=parcela_id).only('establecimiento_id').first()
        if parcela is not None:
            establecimiento_id = parcela.establecimiento_id
    animal.establecimiento_id = establecimiento_id
    animal.madre_id = datos.get('madre_id') or None
    animal.padre_id = datos.get('padre_id') or None
    # La compra/venta asociada se define solo desde sus módulos; acá solo se
    # preserva la existente si el formulario no envía estos campos.
    if 'compra_id' in datos:
        animal.compra_id = datos.get('compra_id') or None
    if 'venta_id' in datos:
        animal.venta_id = datos.get('venta_id') or None
    # El parto solo se toca cuando el formulario lo envía (módulo de Preñez).
    # Evita que la edición de la caravana en Stock desvincule a la cría de su parto.
    if 'parto_id' in datos:
        animal.parto_id = datos.get('parto_id') or None
    animal.descripcion = datos.get('descripcion', '').strip() or None
    if datos.get('eliminar_foto') == '1' and animal.foto:
        animal.foto.delete(save=False)
        animal.foto = None
    if animal.sexo != 'Macho':
        animal.diametro_escrotal = None
    if animal.pk and animal.pk in (animal.madre_id, animal.padre_id):
        raise ValueError('Un animal no puede ser su propio progenitor.')
    if animal.madre_id and (animal.madre.sexo != 'Hembra' or animal.madre.tipo_animal != animal.tipo_animal):
        raise ValueError('La madre seleccionada debe ser hembra y del mismo tipo de animal.')
    if animal.padre_id and (animal.padre.sexo != 'Macho' or animal.padre.tipo_animal != animal.tipo_animal):
        raise ValueError('El padre seleccionado debe ser macho y del mismo tipo de animal.')
    if animal.parto_id:
        parto = Parto.objects.filter(pk=animal.parto_id).first()
        if parto is None:
            raise ValueError('El parto seleccionado no existe.')
        if not parto.vivo:
            raise ValueError('No se puede registrar una cría de un parto con nacido muerto.')


@require_POST
def crear_animal(request):
    try:
        animal = Animal()
        _asignar_campos_animal(animal, request.POST, es_alta=True)
        if not animal.establecimiento_id:
            establecimiento = _establecimiento_actual(request)
            if establecimiento is not None:
                animal.establecimiento_id = establecimiento.id
        _validar_establecimiento_accesible(request, animal.establecimiento_id)
        _validar_parcela_del_establecimiento(request, animal.parcela_id, animal.establecimiento_id)
        if 'foto' in request.FILES and request.FILES['foto']:
            animal.foto = request.FILES['foto']
        animal.full_clean()
        animal.save()
    except (KeyError, ValueError, ValidationError):
        return JsonResponse({'error': 'Completá correctamente los campos obligatorios.'}, status=400)
    except IntegrityError:
        return JsonResponse({'error': 'La caravana SENASA ya se encuentra registrada.'}, status=400)

    return JsonResponse({'id': animal.idAnimal, 'animal': _animal_data(animal)}, status=201)


@require_POST
def actualizar_animal(request, animal_id):
    animal = get_object_or_404(Animal, pk=animal_id, activo=True)
    try:
        _asignar_campos_animal(animal, request.POST)
        _validar_establecimiento_accesible(request, animal.establecimiento_id)
        _validar_parcela_del_establecimiento(request, animal.parcela_id, animal.establecimiento_id)
        if 'foto' in request.FILES and request.FILES['foto']:
            animal.foto = request.FILES['foto']
        animal.full_clean()
        animal.save()
    except (KeyError, ValueError, ValidationError):
        return JsonResponse({'error': 'Completá correctamente los campos obligatorios.'}, status=400)
    except IntegrityError:
        return JsonResponse({'error': 'La caravana SENASA ya se encuentra registrada.'}, status=400)
    return JsonResponse({'animal': _animal_data(animal)})


@require_POST
def eliminar_animal(request, animal_id):
    """Da de baja (lógicamente) un animal: se oculta del sistema pero conserva su historia."""
    animal = get_object_or_404(Animal, pk=animal_id, activo=True)
    animal.activo = False
    animal.save(update_fields=['activo'])
    return JsonResponse({'ok': True})


@require_POST
def crear_parcela(request):
    es_edicion = bool(request.POST.get('id'))
    parcela = None
    try:
        if es_edicion:
            parcela = get_object_or_404(Parcela, pk=request.POST['id'])
        else:
            parcela = Parcela()

        establecimiento_id = request.POST.get('establecimiento_id')
        if not establecimiento_id:
            establecimiento = _establecimiento_actual(request)
            if establecimiento is None:
                establecimiento = Establecimiento.objects.filter(activo=True).order_by('id').first()
            if establecimiento is None:
                establecimiento = Establecimiento.objects.create(
                    nombre='Establecimiento principal',
                    fecha_inicio=date.today(),
                    ubicacion='Sin especificar',
                )
            establecimiento_id = establecimiento.id

        descripcion = request.POST.get('descripcion', '').strip()
        observaciones = request.POST.get('observaciones', '').strip()
        texto_descripcion = ' / '.join([part for part in [descripcion, observaciones] if part]) or None
        parcela.establecimiento_id = establecimiento_id
        parcela.ancho = Decimal(request.POST['ancho'])
        parcela.largo = Decimal(request.POST['largo'])
        parcela.descripcion = texto_descripcion
        parcela.estado = request.POST.get('estado', Parcela.ESTADO_EN_PASTOREO).strip() or Parcela.ESTADO_EN_PASTOREO
        parcela.full_clean()
        parcela.save()
    except (KeyError, ValueError, ValidationError):
        return JsonResponse({'error': 'Completá correctamente el ancho y largo de la parcela.'}, status=400)
    return JsonResponse({'id': parcela.id, 'parcela': _parcela_data(parcela)}, status=200 if es_edicion else 201)


@require_POST
def eliminar_parcela(request, parcela_id):
    parcela = get_object_or_404(Parcela, pk=parcela_id)
    parcela.delete()
    return JsonResponse({'ok': True})


def _registrar_venta(venta, datos, historicos_ids=None):
    """Guarda una venta y todos sus efectos como una única transacción.

    historicos_ids: IDs de los animales que ya formaban parte de esta venta.
    Al editar se conservan aunque ya no estén disponibles (baja lógica, muerte,
    etc.) porque su historia ya quedó ligada a la venta. Solo los animales
    nuevos deben seguir activos, vivos y sin vender.
    """
    try:
        precio_por_kg = Decimal(datos['precio_por_kg'])
        animales_ids = [int(animal_id) for animal_id in datos.getlist('animales')]
    except (KeyError, ValueError, ArithmeticError):
        raise ValueError('Indicá un precio por kilo válido y al menos un animal.')
    if precio_por_kg <= 0 or not animales_ids or len(animales_ids) != len(set(animales_ids)):
        raise ValueError('Indicá un precio por kilo válido y al menos un animal.')

    historicos_ids = {int(animal_id) for animal_id in (historicos_ids or ())}
    animales = list(Animal.objects.select_for_update().filter(pk__in=animales_ids))
    existentes_ids = {animal.idAnimal for animal in animales}
    if any(animal_id not in existentes_ids for animal_id in animales_ids):
        raise ValueError('Uno o más animales ya no existen en el sistema.')
    no_disponibles = [
        animal for animal in animales
        if animal.idAnimal not in historicos_ids and not (animal.activo and animal.vivo and not animal.vendido)
    ]
    if no_disponibles:
        raise ValueError('Uno o más animales ya no están disponibles para la venta.')

    peso_total_manual = _parse_decimal(datos.get('peso_total'))
    peso_manual = str(datos.get('peso_manual', '')).lower() in {'1', 'true', 'on', 'yes'}
    if peso_total_manual is None:
        if any(animal.peso_actual is None or animal.peso_actual <= 0 for animal in animales):
            raise ValueError('Todos los animales seleccionados deben tener un peso actual mayor a cero o indicar un peso total manual.')
        peso_total = sum((animal.peso_actual for animal in animales), Decimal('0'))
    else:
        peso_total = peso_total_manual

    porcentaje_desbaste = _parse_decimal(datos.get('porcentajeDesbaste')) or Decimal('0')
    if not 0 <= porcentaje_desbaste <= 100:
        raise ValueError('El porcentaje de desbaste debe estar entre 0 y 100.')

    estado_cobro = datos.get('estadoDeCobro', 'Pendiente').strip() or 'Pendiente'
    if estado_cobro not in dict(Venta.ESTADO_COBRO_CHOICES):
        raise ValueError('Indicá un estado de cobro válido.')
    metodo_pago = datos.get('metodoDePago', 'Efectivo').strip() or 'Efectivo'
    if metodo_pago not in dict(Venta.METODO_PAGO_CHOICES):
        raise ValueError('Indicá un método de pago válido.')

    peso_desbastado = (peso_total * (1 - porcentaje_desbaste / Decimal('100'))).quantize(Decimal('0.01'))
    monto_total = (peso_desbastado * precio_por_kg).quantize(Decimal('0.01'))
    venta.tipo = datos.get('tipo', 'Venta de animales').strip() or 'Venta de animales'
    venta.fecha = datos.get('fecha') or date.today()
    venta.comprador_id = datos.get('comprador_id') or None
    venta.detalle = datos.get('detalle', '').strip() or None
    venta.peso_total = peso_total
    venta.porcentajeDesbaste = porcentaje_desbaste
    venta.estadoDeCobro = estado_cobro
    venta.metodoDePago = metodo_pago
    venta.precio_por_kg = precio_por_kg
    venta.monto_total = monto_total
    venta.full_clean()
    venta.save()

    establecimiento = next((a.establecimiento for a in animales if a.establecimiento_id is not None), None)
    movimiento, _ = MovimientoFinanciero.objects.update_or_create(
        pk=venta.mov_financiero_id,
        defaults={
            'tipo': 'Ingreso', 'nombre': f'Venta #{venta.id}', 'monto_total': monto_total,
            'fecha': venta.fecha, 'detalle': venta.detalle or f'Venta de {len(animales)} animal(es).',
            'establecimiento': establecimiento, 'activo': True,
        },
    )
    if venta.mov_financiero_id != movimiento.id:
        venta.mov_financiero = movimiento
        venta.save(update_fields=['mov_financiero'])

    for animal in animales:
        if peso_manual:
            precio_venta_animal = ((peso_desbastado / len(animales)) * precio_por_kg).quantize(Decimal('0.01'))
        else:
            factor_desbaste = 1 - porcentaje_desbaste / Decimal('100')
            precio_venta_animal = ((animal.peso_actual or Decimal('0')) * factor_desbaste * precio_por_kg).quantize(Decimal('0.01'))
        animal.vendido = True
        animal.venta = venta
        animal.precio_venta = precio_venta_animal
        animal.save(update_fields=['vendido', 'venta', 'precio_venta'])


def _revertir_venta(venta):
    """Deshace los efectos sobre animales activos para poder editar o eliminar una venta."""
    animales = Animal.objects.select_for_update().filter(venta=venta, activo=True)
    animales.update(vendido=False, venta=None, precio_venta=None)


def _asignar_comprador(comprador, datos):
    comprador.dni = _normalizar_dni(datos.get('dni', ''))
    comprador.nombre = datos['nombre'].strip()
    comprador.apellido = datos.get('apellido', '').strip() or None
    comprador.correo_electronico = datos.get('correo_electronico', '').strip() or None
    comprador.fecha_nacimiento = datos.get('fecha_nacimiento') or None
    comprador.telefono = datos.get('telefono', '').strip()


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def crear_comprador(request):
    try:
        comprador = Comprador()
        _asignar_comprador(comprador, request.POST)
        comprador.full_clean()
        comprador.save()
    except (KeyError, ValueError, ValidationError, IntegrityError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo crear el comprador.'}, status=400)
    return JsonResponse({'id': comprador.id, 'comprador': _comprador_data(comprador)}, status=201)


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def actualizar_comprador(request, comprador_id):
    comprador = get_object_or_404(Comprador, pk=comprador_id, activo=True)
    try:
        _asignar_comprador(comprador, request.POST)
        comprador.full_clean()
        comprador.save()
    except (KeyError, ValueError, ValidationError, IntegrityError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo actualizar el comprador.'}, status=400)
    return JsonResponse({'comprador': _comprador_data(comprador)})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def eliminar_comprador(request, comprador_id):
    comprador = get_object_or_404(Comprador, pk=comprador_id, activo=True)
    comprador.activo = False
    comprador.save(update_fields=['activo'])
    return JsonResponse({'ok': True})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def crear_venta(request):
    try:
        with transaction.atomic():
            venta = Venta()
            _registrar_venta(venta, request.POST)
    except (ValueError, ValidationError, IntegrityError, ArithmeticError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo registrar la venta.'}, status=400)
    return JsonResponse({'id': venta.id, 'venta': _venta_data(venta)}, status=201)


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def actualizar_venta(request, venta_id):
    try:
        with transaction.atomic():
            venta = get_object_or_404(Venta.objects.select_for_update(), pk=venta_id, activo=True)
            historicos_ids = set(venta.animal_set.values_list('pk', flat=True))
            _revertir_venta(venta)
            _registrar_venta(venta, request.POST, historicos_ids=historicos_ids)
    except (ValueError, ValidationError, IntegrityError, ArithmeticError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo actualizar la venta.'}, status=400)
    return JsonResponse({'venta': _venta_data(venta)})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def eliminar_venta(request, venta_id):
    """Da de baja (lógicamente) una venta y su movimiento financiero asociado."""
    with transaction.atomic():
        venta = get_object_or_404(Venta.objects.select_for_update(), pk=venta_id, activo=True)
        movimiento_id = venta.mov_financiero_id
        _revertir_venta(venta)
        venta.activo = False
        venta.save(update_fields=['activo'])
        if movimiento_id:
            MovimientoFinanciero.objects.filter(pk=movimiento_id, activo=True).update(activo=False)
    return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
# Módulo de Compras
# ---------------------------------------------------------------------------

def _obtener_o_crear_insumo(datos):
    """Devuelve el insumo elegido, o crea uno nuevo con el nombre indicado."""
    insumo_id = datos.get('insumo_id')
    nuevo_nombre = datos.get('nuevo_insumo', '').strip()
    tipo_insumo = datos.get('tipo_insumo', '').strip()
    if insumo_id:
        insumo = Insumo.objects.filter(pk=insumo_id).first()
        if insumo is None:
            raise ValueError('El insumo seleccionado ya no existe.')
        return insumo
    if nuevo_nombre:
        insumo, _ = Insumo.objects.get_or_create(
            nombre__iexact=nuevo_nombre,
            defaults={'nombre': nuevo_nombre, 'tipo': tipo_insumo or None},
        )
        if insumo.tipo != tipo_insumo:
            insumo.tipo = tipo_insumo or None
            insumo.save(update_fields=['tipo'])
        return insumo
    raise ValueError('Seleccioná un insumo o indicá el nombre de uno nuevo.')


def _detalle_efectos_compra(compra):
    """Texto con las especificaciones de la compra para el movimiento financiero."""
    detalle = compra.detalle or ''
    detalle = detalle.strip() + ('\n' if detalle else '')
    lote = compra.detalles.select_related('lote__insumo').first()
    if lote is not None and lote.lote is not None:
        insumo = lote.lote.insumo
        nombre_insumo = insumo.nombre if insumo else 'Insumo'
        detalle += f'Insumo: {nombre_insumo} | Cantidad: {lote.cantidad} | Precio unitario: ${lote.precioUnitario}'
        if lote.lote.nombre:
            detalle += f' | Lote: {lote.lote.nombre}'
        if lote.lote.fechaVencimiento:
            detalle += f' | Vence: {lote.lote.fechaVencimiento}'
    animal = compra.animal_set.first()
    if animal is not None:
        detalle += (f'Animal: {animal.nombre or "S/N"} | Caravana: {_caravana_text(animal)} | '
                    f'{animal.tipo_animal} {animal.sexo}')
        if animal.raza:
            detalle += f' | Raza: {animal.raza}'
        if animal.fecha_nacimiento:
            detalle += f' | Nacimiento: {animal.fecha_nacimiento}'
    return detalle.strip() or None


def _animal_sin_dependencias(animal):
    """¿Puede eliminarse el animal sin perder historial de otros módulos?"""
    if Diagnostico.objects.filter(animal=animal).exists():
        return False
    if DetalleEvento.objects.filter(animal=animal).exists():
        return False
    if Preniez.objects.filter(madre=animal).exists():
        return False
    return True


def _sincronizar_efectos_compra(compra, tipo):
    """Elimina o desvincula el lote/animal que no corresponda al tipo de compra."""
    if compra.pk is None:
        return
    if tipo != 'Insumos':
        for detalle in list(compra.detalles.all()):
            lote = detalle.lote
            detalle.delete()
            if lote is not None and not DetalleCompra.objects.filter(lote=lote).exists():
                if not Consumo.objects.filter(lote=lote).exists():
                    lote.delete()
    if tipo != 'Animales':
        for animal in Animal.objects.filter(compra=compra):
            if animal.vendido:
                animal.compra = None
                animal.save(update_fields=['compra'])
            elif _animal_sin_dependencias(animal):
                animal.delete()
            else:
                animal.compra = None
                animal.save(update_fields=['compra'])


def _registrar_compra(compra, datos, establecimiento=None):
    """Guarda una compra, sus efectos (lote/animal) y el movimiento financiero en una transacción."""
    tipo = datos.get('tipo', '').strip()
    if tipo not in dict(Compra.TIPO_CHOICES):
        raise ValueError('Indicá un tipo de compra válido.')

    compra.tipo = tipo
    compra.fecha = datos.get('fecha') or date.today()
    compra.proveedor_id = datos.get('proveedor_id') or None
    compra.detalle = datos.get('detalle', '').strip() or None

    estado_pago = datos.get('estadoDePago', 'Pendiente').strip() or 'Pendiente'
    if estado_pago not in dict(Compra.ESTADO_PAGO_CHOICES):
        raise ValueError('Indicá un estado de pago válido.')
    metodo_pago = datos.get('metodoDePago', 'Efectivo').strip() or 'Efectivo'
    if metodo_pago not in dict(Compra.METODO_PAGO_CHOICES):
        raise ValueError('Indicá un método de pago válido.')
    compra.estadoDePago = estado_pago
    compra.metodoDePago = metodo_pago

    _sincronizar_efectos_compra(compra, tipo)

    if tipo == 'Insumos':
        cantidad = _parse_decimal(datos.get('cantidad'))
        precio_unitario = _parse_decimal(datos.get('precio_unitario'))
        if cantidad is None or precio_unitario is None or cantidad <= 0 or precio_unitario <= 0:
            raise ValueError('Indicá cantidad y precio unitario válidos del insumo.')
        monto = (cantidad * precio_unitario).quantize(Decimal('0.01'))
        compra.monto_total = monto
        compra.full_clean()
        compra.save()

        insumo = _obtener_o_crear_insumo(datos)
        detalle = compra.detalles.select_related('lote').first()
        lote = detalle.lote if detalle is not None else Lote()
        lote.insumo = insumo
        lote.nombre = datos.get('lote_nombre', '').strip() or None
        lote.fechaVencimiento = datos.get('fecha_vencimiento') or None
        lote.stockActual = cantidad
        if establecimiento is not None:
            lote.establecimiento = establecimiento
        lote.save()
        DetalleCompra.objects.update_or_create(
            compra=compra,
            defaults={'cantidad': cantidad, 'precioUnitario': precio_unitario, 'lote': lote},
        )
    elif tipo == 'Animales':
        monto = _parse_decimal(datos.get('monto_total')) or _parse_decimal(datos.get('costo_adquisicion'))
        if monto is None or monto <= 0:
            raise ValueError('Indicá un monto total válido.')
        compra.monto_total = monto
        compra.full_clean()
        compra.save()

        animal = Animal.objects.filter(compra=compra).first()
        animal = animal if animal is not None else Animal(compra=compra)
        _asignar_campos_animal(animal, datos, es_alta=True)
        if animal.compra_id != compra.id:
            animal.compra = compra
        if not animal.establecimiento_id and establecimiento is not None:
            animal.establecimiento = establecimiento
        if not animal.vivo:
            animal.vivo = True
        animal.costo_adquisicion = monto
        animal.full_clean()
        animal.save()
    else:
        monto = _parse_decimal(datos.get('monto_total'))
        if monto is None or monto <= 0:
            raise ValueError('Indicá un monto total válido.')
        compra.monto_total = monto
        compra.full_clean()
        compra.save()

    movimiento, _ = MovimientoFinanciero.objects.update_or_create(
        pk=compra.mov_financiero_id,
        defaults={
            'tipo': 'Egreso', 'nombre': f'Compra #{compra.id} - {tipo}',
            'monto_total': compra.monto_total, 'fecha': compra.fecha,
            'detalle': _detalle_efectos_compra(compra),
            'establecimiento': establecimiento, 'activo': True,
        },
    )
    if compra.mov_financiero_id != movimiento.id:
        compra.mov_financiero = movimiento
        compra.save(update_fields=['mov_financiero'])


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def crear_compra(request):
    try:
        with transaction.atomic():
            compra = Compra()
            _registrar_compra(compra, request.POST, establecimiento=_establecimiento_actual(request))
    except (ValueError, ValidationError, IntegrityError, ArithmeticError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo registrar la compra.'}, status=400)
    return JsonResponse({'id': compra.id, 'compra': _compra_data(compra)}, status=201)


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def actualizar_compra(request, compra_id):
    try:
        with transaction.atomic():
            compra = get_object_or_404(Compra.objects.select_for_update(), pk=compra_id, activo=True)
            _registrar_compra(compra, request.POST, establecimiento=_establecimiento_actual(request))
    except (ValueError, ValidationError, IntegrityError, ArithmeticError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo actualizar la compra.'}, status=400)
    return JsonResponse({'compra': _compra_data(compra)})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def eliminar_compra(request, compra_id):
    """Da de baja (lógicamente) una compra y su movimiento financiero asociado."""
    with transaction.atomic():
        compra = get_object_or_404(Compra.objects.select_for_update(), pk=compra_id, activo=True)
        movimiento_id = compra.mov_financiero_id
        # Se desvincula a los animales de la compra sin borrarlos físicamente.
        Animal.objects.filter(compra=compra).update(compra=None)
        compra.activo = False
        compra.save(update_fields=['activo'])
        if movimiento_id:
            MovimientoFinanciero.objects.filter(pk=movimiento_id, activo=True).update(activo=False)
    return JsonResponse({'ok': True})


def _asignar_proveedor(proveedor, datos):
    proveedor.dni = _normalizar_dni(datos.get('dni', ''))
    proveedor.nombre = datos['nombre'].strip()
    proveedor.apellido = datos.get('apellido', '').strip() or None
    proveedor.correo_electronico = datos.get('correo_electronico', '').strip() or None
    proveedor.fecha_nacimiento = datos.get('fecha_nacimiento') or None
    proveedor.telefono = datos.get('telefono', '').strip()


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def crear_proveedor(request):
    try:
        proveedor = Proveedor()
        _asignar_proveedor(proveedor, request.POST)
        proveedor.full_clean()
        proveedor.save()
    except (KeyError, ValueError, ValidationError, IntegrityError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo crear el proveedor.'}, status=400)
    return JsonResponse({'id': proveedor.id, 'proveedor': _proveedor_data(proveedor)}, status=201)


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def actualizar_proveedor(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, pk=proveedor_id, activo=True)
    try:
        _asignar_proveedor(proveedor, request.POST)
        proveedor.full_clean()
        proveedor.save()
    except (KeyError, ValueError, ValidationError, IntegrityError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo actualizar el proveedor.'}, status=400)
    return JsonResponse({'proveedor': _proveedor_data(proveedor)})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def eliminar_proveedor(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, pk=proveedor_id, activo=True)
    proveedor.activo = False
    proveedor.save(update_fields=['activo'])
    return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
# Módulo de Liquidación de Sueldos
# ---------------------------------------------------------------------------

def _empleados_de(request):
    """Usuarios con rol en el establecimiento activo (candidatos a liquidar sueldos)."""
    establecimiento = _establecimiento_actual(request)
    queryset = Usuario.objects.filter(activo=True).select_related('persona').order_by('persona__nombre')
    if establecimiento is not None:
        queryset = queryset.filter(rolestablecimiento__establecimiento=establecimiento).distinct()
    return list(queryset)


def _empleado_data(usuario):
    return {
        'id': usuario.id,
        'nombre': f'{usuario.persona.nombre} {usuario.persona.apellido or ""}'.strip(),
        'usuario': usuario.nombre_usuario,
    }


def _liquidacion_data(liquidacion):
    empleado = liquidacion.empleado
    nombre_empleado = (
        f'{empleado.persona.nombre} {empleado.persona.apellido or ""}'.strip()
        if empleado else 'S/N'
    )
    return {
        'id': liquidacion.idLiquidacion,
        'fecha': _to_iso_date(liquidacion.fecha),
        'sueldo': str(liquidacion.sueldo),
        'descripcion': liquidacion.descripcion or '',
        'empleado_id': liquidacion.empleado_id,
        'empleado': nombre_empleado,
        'empleado_usuario': empleado.nombre_usuario if empleado else '',
        'establecimiento_id': liquidacion.establecimiento_id,
        'establecimiento': liquidacion.establecimiento.nombre if liquidacion.establecimiento else '',
        'movimiento_financiero_id': liquidacion.movimiento_financiero_id,
    }


def _registrar_liquidacion(liquidacion, datos, establecimiento=None):
    """Guarda una liquidación de sueldo y su egreso financiero en una transacción."""
    fecha = datos.get('fecha') or date.today()
    sueldo = _parse_decimal(datos.get('sueldo'))
    empleado_id = datos.get('empleado_id')
    if not fecha:
        raise ValueError('Indicá la fecha de la liquidación.')
    if sueldo is None or sueldo <= 0:
        raise ValueError('Indicá un monto de sueldo válido.')
    if not empleado_id:
        raise ValueError('Seleccioná el empleado a liquidar.')

    empleado = Usuario.objects.select_related('persona').filter(pk=empleado_id, activo=True).first()
    if empleado is None:
        raise ValueError('El empleado seleccionado ya no existe.')
    if establecimiento is not None:
        pertenece = RolEstablecimiento.objects.filter(
            usuario=empleado, establecimiento=establecimiento
        ).exists()
        if not pertenece:
            raise ValueError('El empleado seleccionado no pertenece al establecimiento activo.')

    liquidacion.fecha = fecha
    liquidacion.sueldo = sueldo
    liquidacion.descripcion = datos.get('descripcion', '').strip() or None
    liquidacion.empleado = empleado
    if establecimiento is not None:
        liquidacion.establecimiento = establecimiento
    elif liquidacion.establecimiento_id is None:
        raise ValueError('No hay ningún establecimiento activo para registrar el egreso.')

    liquidacion.full_clean()
    liquidacion.save()

    nombre_empleado = f'{empleado.persona.nombre} {empleado.persona.apellido or ""}'.strip()
    nombre = f'Sueldo - {nombre_empleado}'
    if len(nombre) > 100:
        nombre = nombre[:99] + '…'

    movimiento, _ = MovimientoFinanciero.objects.update_or_create(
        pk=liquidacion.movimiento_financiero_id,
        defaults={
            'tipo': 'Egreso', 'nombre': nombre,
            'monto_total': sueldo, 'fecha': fecha,
            'detalle': liquidacion.descripcion,
            'establecimiento': liquidacion.establecimiento,
            'activo': True,
        },
    )
    if liquidacion.movimiento_financiero_id != movimiento.id:
        liquidacion.movimiento_financiero = movimiento
        liquidacion.save(update_fields=['movimiento_financiero'])


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def crear_liquidacion(request):
    try:
        with transaction.atomic():
            liquidacion = LiquidacionSueldo()
            _registrar_liquidacion(liquidacion, request.POST, establecimiento=_establecimiento_actual(request))
    except (ValueError, ValidationError, IntegrityError, ArithmeticError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo registrar la liquidación.'}, status=400)
    return JsonResponse({'id': liquidacion.idLiquidacion, 'liquidacion': _liquidacion_data(liquidacion)}, status=201)


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def actualizar_liquidacion(request, liquidacion_id):
    try:
        with transaction.atomic():
            liquidacion = get_object_or_404(LiquidacionSueldo.objects.select_for_update(), pk=liquidacion_id)
            _registrar_liquidacion(liquidacion, request.POST, establecimiento=_establecimiento_actual(request))
    except (ValueError, ValidationError, IntegrityError, ArithmeticError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo actualizar la liquidación.'}, status=400)
    return JsonResponse({'liquidacion': _liquidacion_data(liquidacion)})


@require_POST
@rol_requerido(ROL_PROPIETARIO)
def eliminar_liquidacion(request, liquidacion_id):
    with transaction.atomic():
        liquidacion = get_object_or_404(LiquidacionSueldo.objects.select_for_update(), pk=liquidacion_id)
        movimiento_id = liquidacion.movimiento_financiero_id
        if movimiento_id:
            # Se desvincula y se da de baja lógicamente el movimiento asociado.
            LiquidacionSueldo.objects.filter(pk=liquidacion.pk).update(movimiento_financiero=None)
            liquidacion.movimiento_financiero = None
            MovimientoFinanciero.objects.filter(pk=movimiento_id, activo=True).update(activo=False)
        liquidacion.delete()
    return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
# Módulo de Preñez y Partos
# ---------------------------------------------------------------------------

GESTACION_MESES = {
    'Bovino': 9,
    'Ovino': 5,
    'Porcino': 3,  # + 3 semanas
}

MESES_NOMBRE = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]


def _sumar_meses(fecha, meses):
    mes = fecha.month + meses
    anio = fecha.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def _fecha_estimada_parto(preniez):
    """Estima la fecha de parto según la especie de la madre.
    Bovino: 9 meses · Porcino: 3 meses y 3 semanas · Ovino: 5 meses."""
    tipo = preniez.madre.tipo_animal if preniez.madre else 'Bovino'
    if tipo == 'Porcino':
        return _sumar_meses(preniez.fecha, 3) + timedelta(days=21)
    return _sumar_meses(preniez.fecha, GESTACION_MESES.get(tipo, 9))


def _mes_semana_parto(fecha):
    return f"{MESES_NOMBRE[fecha.month]} · Semana {(fecha.day - 1) // 7 + 1}"


def _faltante_parto(fecha_estimada):
    """Muestra cuánto falta para el parto: meses y semanas, o semanas y días si falta poco."""
    hoy = date.today()
    if fecha_estimada < hoy:
        return 'Vencido'
    dias = (fecha_estimada - hoy).days
    if dias >= 30:
        meses = dias // 30
        semanas = (dias % 30) // 7
        return f'{meses} meses y {semanas} semanas'
    semanas = dias // 7
    return f'{semanas} semanas y {dias % 7} días'


def _preniez_data(p):
    fecha_estimada = _fecha_estimada_parto(p)
    crias = [{
        'id': c.idAnimal,
        'nombre': c.nombre or 'S/N',
        'caravana': str(c.id_senasa) if c.id_senasa is not None else 'S/N',
        'sexo': c.sexo,
    } for c in p.parto.crias.all()] if p.parto_id else []
    evento = p.evento_sanitario
    return {
        'id': p.id,
        'fecha': p.fecha.isoformat(),
        'tipo': p.tipo,
        'estado_actual': p.estado_actual,
        'detalle': p.detalle or '',
        'madre_id': p.madre_id,
        'madre_nombre': p.madre.nombre or 'S/N',
        'madre_caravana': str(p.madre.id_senasa) if p.madre.id_senasa is not None else 'Sin caravana',
        'madre_tipo': p.madre.tipo_animal,
        'madre_parcela': str(p.madre.parcela) if p.madre.parcela else 'Sin asignar',
        'padre_id': p.padre_id,
        'padre': str(p.padre) if p.padre else 'No registrado',
        'padre_donante': p.padre_donante or '',
        'evento_sanitario_id': p.evento_sanitario_id,
        'evento_fecha': evento.fecha_aplicacion.isoformat() if evento else '',
        'evento_veterinario': str(evento.veterinario) if evento and evento.veterinario else '-',
        'evento_costo': str(evento.costo_total) if evento and evento.costo_total else '',
        'parto_id': p.parto_id,
        'parto_fecha': p.parto.fecha.isoformat() if p.parto_id else '',
        'parto_vivo': p.parto.vivo if p.parto_id else None,
        'crias': crias,
        'fecha_estimada': fecha_estimada.isoformat(),
        'fecha_estimada_text': fecha_estimada.strftime('%d/%m/%Y'),
        'mes_semana_parto': _mes_semana_parto(fecha_estimada),
        'faltante_parto': _faltante_parto(fecha_estimada),
    }


def _parto_data(parto):
    preniez = getattr(parto, 'preniez', None)
    madre = preniez.madre if preniez else None
    return {
        'id': parto.id,
        'fecha': parto.fecha.isoformat(),
        'vivo': parto.vivo,
        'preniez_id': preniez.id if preniez else None,
        'madre_id': madre.idAnimal if madre else None,
        'madre_nombre': (madre.nombre or 'S/N') if madre else '-',
        'madre_caravana': str(madre.id_senasa) if madre and madre.id_senasa is not None else 'Sin caravana',
        'madre_tipo': madre.tipo_animal if madre else '',
        'tipo_preñez': preniez.tipo if preniez else '',
        'crias': [{
            'id': c.idAnimal,
            'nombre': c.nombre or 'S/N',
            'caravana': str(c.id_senasa) if c.id_senasa is not None else 'S/N',
            'sexo': c.sexo,
        } for c in parto.crias.all()],
    }


def _evento_inseminacion_data(evento):
    """Datos de un evento sanitario de tipo 'Inseminación' para el módulo de Preñez."""
    detalles = list(evento.detalles.select_related('animal').order_by('animal__id_senasa'))
    ids = [d.animal_id for d in detalles]
    prenies_del_evento = {p.madre_id: p for p in evento.prenieces.all()}
    activas = set(Preniez.objects.filter(madre_id__in=ids, estado_actual='Preñada', parto__isnull=True)
                  .values_list('madre_id', flat=True))
    # Una hembra con preñez originada en este evento (aunque el parto ya se
    # haya registrado) no puede volver a marcarse como preñada en el mismo
    # evento. El vínculo por evento_sanitario es estable: no depende de la
    # caravana ni del estado actual de la preñez.
    con_preniez_del_evento = set(prenies_del_evento.keys())
    animales = []
    for detalle in detalles:
        a = detalle.animal
        preniez = prenies_del_evento.get(a.idAnimal)
        animales.append({
            'id': a.idAnimal,
            'nombre': a.nombre or 'S/N',
            'caravana': str(a.id_senasa) if a.id_senasa is not None else 'S/N',
            'tipo': a.tipo_animal,
            'preniada': a.idAnimal in activas or a.idAnimal in con_preniez_del_evento,
            'parida': bool(preniez and preniez.parto_id),
            'parto_fecha': preniez.parto.fecha.isoformat() if preniez and preniez.parto_id else '',
            'de_este_evento': bool(preniez),
            'preniez_id': preniez.id if preniez else None,
        })
    return {
        'id': evento.id,
        'fecha_aplicacion': evento.fecha_aplicacion.isoformat(),
        'estado': evento.estado,
        'padre_id': evento.padre_id,
        'padre': str(evento.padre) if evento.padre_id else '-',
        'padre_donante': evento.padre_donante or '',
        'veterinario_id': evento.veterinario_id,
        'veterinario': str(evento.veterinario) if evento.veterinario else '-',
        'costo_total': str(evento.costo_total or ''),
        'detalle': evento.detalle or '',
        'animales': animales,
        'total_hembras': len(animales),
        'preñadas': sum(1 for x in animales if x['preniada']),
    }


def prenieces(request):
    today = date.today()
    prenieces_qs = Preniez.objects.select_related('madre__parcela', 'padre', 'parto', 'evento_sanitario__veterinario') \
        .prefetch_related('parto__crias').order_by('-fecha', '-id')
    prenieces_list = list(prenieces_qs)

    preniadas = [p for p in prenieces_list if p.estado_actual == 'Preñada' and p.parto_id is None]
    proximo = None
    for p in preniadas:
        estimada = _fecha_estimada_parto(p)
        if proximo is None or estimada < proximo[0]:
            proximo = (estimada, p)

    madres = Animal.objects.filter(activo=True, sexo='Hembra', vivo=True, vendido=False) \
        .select_related('parcela').order_by('id_senasa')
    madres_preniadas = set(Preniez.objects.filter(estado_actual='Preñada', parto__isnull=True)
                           .values_list('madre_id', flat=True))
    padres = Animal.objects.filter(activo=True, sexo='Macho', vivo=True, vendido=False).order_by('id_senasa')
    veterinarios = Veterinario.objects.filter(activo=True).order_by('apellido', 'nombre')
    partos = Parto.objects.select_related('preniez__madre', 'preniez__padre') \
        .prefetch_related('crias').order_by('-fecha', '-id')
    eventos_inseminacion = EventoSanitario.objects.filter(tipo='Inseminación', activo=True) \
        .select_related('padre', 'veterinario') \
        .prefetch_related('detalles__animal', 'prenieces') \
        .order_by('-fecha_aplicacion', '-id')

    return _page(request, 'prenieces.html', 'prenieces', {
        'kpis': {
            'partos_anio': Parto.objects.filter(fecha__year=today.year).count(),
            'vacas_preniadas': len(preniadas),
            'total_prenieces': len(prenieces_list),
            'proximo_parto': proximo[0].strftime('%d/%m/%Y') if proximo else '-',
            'proximo_parto_animal': (f"{proximo[1].madre.nombre or 'S/N'} "
                                     f"#{proximo[1].madre.id_senasa if proximo[1].madre.id_senasa is not None else 'S/C'} · "
                                     f"en {(proximo[0] - today).days} días")
                                     if proximo else '',
            'proximo_parto_dias': (proximo[0] - today).days if proximo else None,
        },
        'prenieces': [_preniez_data(p) for p in prenieces_list],
        'partos': [_parto_data(p) for p in partos],
        'eventos_inseminacion': [_evento_inseminacion_data(e) for e in eventos_inseminacion],
        'madres': [{
            'id': a.idAnimal,
            'caravana': str(a.id_senasa) if a.id_senasa is not None else 'S/C',
            'nombre': a.nombre or 'S/N',
            'tipo': a.tipo_animal,
            'parcela': str(a.parcela) if a.parcela else 'Sin asignar',
            'preniada': a.idAnimal in madres_preniadas,
        } for a in madres],
        'padres': [{
            'id': a.idAnimal,
            'nombre': f'#{a.id_senasa if a.id_senasa is not None else "S/C"} — {a.nombre or "S/N"}',
            'tipo': a.tipo_animal,
        } for a in padres],
        'veterinarios': [_veterinario_data(v) for v in veterinarios],
        'tipos': [c[0] for c in Preniez.TIPO_CHOICES],
        'estados': [c[0] for c in Preniez.ESTADO_CHOICES],
        'especies': [c[0] for c in Animal.TIPO_CHOICES],
    })


def _asignar_preniez(preniez, datos):
    preniez.fecha = date.fromisoformat(datos['fecha'])
    preniez.tipo = datos['tipo']
    preniez.estado_actual = datos.get('estado_actual', 'Preñada')
    preniez.detalle = datos.get('detalle', '').strip() or None
    preniez.madre_id = int(datos['madre_id'])
    preniez.padre_id = int(datos['padre_id']) if datos.get('padre_id') else None
    preniez.padre_donante = datos.get('padre_donante', '').strip() or None

    madre = Animal.objects.select_related('parcela').filter(pk=preniez.madre_id, activo=True).first()
    if madre is None or madre.sexo != 'Hembra':
        raise ValueError('Seleccioná un animal hembra para cargar la preñez.')
    if not madre.vivo or madre.vendido:
        raise ValueError('El animal debe estar vivo y no vendido.')
    if preniez.pk is None and Preniez.objects.filter(
            madre_id=preniez.madre_id, estado_actual='Preñada', parto__isnull=True).exists():
        raise ValueError('El animal ya tiene una preñez activa registrada.')
    if preniez.padre_id and preniez.padre.sexo != 'Macho':
        raise ValueError('El padre seleccionado debe ser macho.')
    if preniez.padre_id and preniez.padre.tipo_animal != madre.tipo_animal:
        raise ValueError('El padre debe ser del mismo tipo de animal que la madre.')


@require_POST
def crear_preniez(request):
    try:
        with transaction.atomic():
            preniez = Preniez()
            _asignar_preniez(preniez, request.POST)
            preniez.full_clean()
            preniez.save()
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'preniez': _preniez_data(preniez)}, status=201)


@require_POST
def actualizar_preniez(request, preniez_id):
    preniez = get_object_or_404(Preniez.objects.select_for_update(), pk=preniez_id)
    try:
        with transaction.atomic():
            _asignar_preniez(preniez, request.POST)
            preniez.full_clean()
            preniez.save()
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'preniez': _preniez_data(preniez)})


@require_POST
def eliminar_preniez(request, preniez_id):
    preniez = get_object_or_404(Preniez.objects.select_for_update(), pk=preniez_id)
    with transaction.atomic():
        parto = preniez.parto
        if parto:
            Animal.objects.filter(parto=parto).update(parto=None)
            parto.delete()
        preniez.delete()
    return JsonResponse({'ok': True})


@require_POST
def finalizar_preniez(request, preniez_id):
    """Carga el parto de la preñez. Si el parto fue vivo, la cría se registra aparte."""
    try:
        with transaction.atomic():
            preniez = get_object_or_404(Preniez.objects.select_for_update(), pk=preniez_id)
            if preniez.parto_id:
                raise ValueError('Esta preñez ya tiene un parto cargado.')
            parto = Parto.objects.create(
                fecha=date.fromisoformat(request.POST['fecha']),
                vivo=request.POST.get('vivo') in ('true', 'on', '1', 'True'),
            )
            preniez.parto = parto
            preniez.save(update_fields=['parto'])
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({
        'preniez': _preniez_data(preniez),
        'parto': {'id': parto.id, 'fecha': parto.fecha.isoformat(), 'vivo': parto.vivo},
    }, status=201)


@require_POST
def crear_evento_inseminacion(request):
    """Registra un evento sanitario de tipo 'Inseminación' para varias hembras."""
    try:
        datos = request.POST.copy()
        datos['tipo'] = 'Inseminación'
        evento = EventoSanitario()
        animal_ids = _asignar_evento_sanitario(evento, datos)
        _validar_inseminacion(evento, animal_ids, datos.get('tipo_animal', ''))
        evento.full_clean()
        with transaction.atomic():
            evento.save()
            _sync_detalles(evento, animal_ids)
            _sync_movimiento_evento(evento)
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'evento': _evento_inseminacion_data(evento)}, status=201)


def _validar_inseminacion(evento, animal_ids, tipo_animal='', ids_ya_en_evento=None):
    if not tipo_animal or tipo_animal not in [c[0] for c in Animal.TIPO_CHOICES]:
        raise ValueError('Seleccioná el tipo de animal para la inseminación.')
    if evento.padre_id:
        padre = Animal.objects.filter(pk=evento.padre_id, activo=True).first()
        if padre is None or padre.sexo != 'Macho':
            raise ValueError('El padre seleccionado debe ser macho.')
        if padre.tipo_animal != tipo_animal:
            raise ValueError('El padre debe ser del mismo tipo de animal que las hembras a inseminar.')
    # Los animales que ya integraban el evento se conservan aunque estén dados
    # de baja; solo se validan (hembra, misma especie) los animales nuevos.
    ya_en_evento = set(ids_ya_en_evento or ())
    nuevos = [aid for aid in animal_ids if aid not in ya_en_evento]
    if nuevos:
        if Animal.objects.filter(activo=True, pk__in=nuevos, sexo='Hembra').count() != len(nuevos):
            raise ValueError('Solo se pueden inseminar animales hembra.')
        if Animal.objects.filter(activo=True, pk__in=nuevos).exclude(tipo_animal=tipo_animal).exists():
            raise ValueError('Todas las hembras deben ser del mismo tipo de animal que el seleccionado.')


@require_POST
def actualizar_evento_inseminacion(request, evento_id):
    evento = get_object_or_404(EventoSanitario, pk=evento_id)
    if evento.tipo != 'Inseminación':
        return JsonResponse({'error': 'El evento no es una inseminación.'}, status=400)
    try:
        datos = request.POST.copy()
        datos['tipo'] = 'Inseminación'
        animal_ids = _asignar_evento_sanitario(evento, datos)
        _validar_inseminacion(
            evento, animal_ids, datos.get('tipo_animal', ''),
            ids_ya_en_evento=evento.detalles.values_list('animal_id', flat=True),
        )
        evento.full_clean()
        with transaction.atomic():
            evento.save()
            _sync_detalles(evento, animal_ids)
            _sync_movimiento_evento(evento)
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'evento': _evento_inseminacion_data(evento)})


@require_POST
def eliminar_evento_inseminacion(request, evento_id):
    """Da de baja (lógicamente) un evento de inseminación y su movimiento financiero asociado."""
    evento = get_object_or_404(EventoSanitario, pk=evento_id, activo=True)
    if evento.tipo != 'Inseminación':
        return JsonResponse({'error': 'El evento no es una inseminación.'}, status=400)
    if evento.prenieces.exists():
        return JsonResponse({
            'error': 'No se puede eliminar el evento: tiene preñadas asociadas. Eliminá primero esas preñeces.',
        }, status=400)
    with transaction.atomic():
        movimiento_id = evento.mov_financiero_id
        evento.activo = False
        evento.save(update_fields=['activo'])
        if movimiento_id:
            MovimientoFinanciero.objects.filter(pk=movimiento_id, activo=True).update(activo=False)
    return JsonResponse({'ok': True})


@require_POST
def registrar_preniadas(request, evento_id):
    """Marca las hembras de la inseminación que quedaron preñadas y crea sus preñeces."""
    evento = get_object_or_404(EventoSanitario.objects.select_related('padre', 'veterinario'), pk=evento_id)
    if evento.tipo != 'Inseminación':
        return JsonResponse({'error': 'El evento no es una inseminación.'}, status=400)
    animal_ids = [int(value) for value in request.POST.getlist('animales') if str(value).strip()]
    validos = set(evento.detalles.values_list('animal_id', flat=True))
    if not animal_ids:
        return JsonResponse({'error': 'Seleccioná al menos una hembra preñada.'}, status=400)
    if not set(animal_ids).issubset(validos):
        return JsonResponse({'error': 'Una de las hembras no pertenece a esta inseminación.'}, status=400)
    try:
        with transaction.atomic():
            creadas = []
            for animal_id in animal_ids:
                # Ya tiene una preñez originada en este evento (aunque su parto
                # ya esté registrado): no se vuelve a marcar como preñada.
                if Preniez.objects.filter(madre_id=animal_id, evento_sanitario=evento).exists():
                    continue
                if Preniez.objects.filter(madre_id=animal_id, estado_actual='Preñada', parto__isnull=True).exists():
                    continue
                creadas.append(Preniez.objects.create(
                    fecha=evento.fecha_aplicacion,
                    tipo='Inseminación',
                    estado_actual='Preñada',
                    madre_id=animal_id,
                    padre=evento.padre,
                    padre_donante=evento.padre_donante,
                    detalle=f'Preñada registrada desde la inseminación #{evento.id}.',
                    evento_sanitario=evento,
                ))
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({
        'evento': _evento_inseminacion_data(evento),
        'prenieces': [_preniez_data(p) for p in creadas],
    }, status=201)
