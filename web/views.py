import calendar
import json
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Sum, Q
from django.db import transaction
from django.http import JsonResponse
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from animales.models import Animal, MovimientoAnimal, Pesaje
from establecimientos.models import Parcela
from finanzas.models import Compra, MovimientoFinanciero, Venta
from inventario.models import Dieta, Insumo, Lote, Consumo
from sanidad.models import DetalleEvento, EventoSanitario, Enfermedad, Diagnostico
from usuarios.models import Comprador, RolEstablecimiento, Usuario, Veterinario


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
        'id': animal.id, 'caravana': _caravana_text(animal), 'nombre': animal.nombre or 'S/N',
        'categoria': _categoria(animal), 'sexo': animal.sexo, 'raza': animal.raza or '-',
        'edad': _edad(animal), 'peso': f"{animal.peso_actual or 0} kg",
        'parcela': str(animal.parcela) if animal.parcela else 'Sin asignar',
        'parcela_id': animal.parcela_id,
        'estado': estado, 'ingreso': animal.fecha_nacimiento.isoformat() if animal.fecha_nacimiento else '-',
        'notas': animal.descripcion or '-',
        'tipo_animal': animal.tipo_animal, 'peso_al_nacer': str(animal.peso_al_nacer or ''),
        'peso_al_destete': str(animal.peso_al_destete or ''), 'peso_actual_valor': str(animal.peso_actual or ''),
        'vendido': animal.vendido, 'vivo': animal.vivo, 'enfermo': animal.enfermo, 'castrado': animal.castrado,
        'costo_adquisicion': str(animal.costo_adquisicion or ''), 'precio_venta': str(animal.precio_venta or ''),
        'color': animal.color or '', 'diametro_escrotal': str(animal.diametro_escrotal or ''),
        'dieta_id': animal.dieta_id, 'dieta': str(animal.dieta) if animal.dieta else 'Sin dieta',
        'madre_id': animal.madre_id, 'madre': str(animal.madre) if animal.madre else 'No registrada',
        'padre_id': animal.padre_id, 'padre': str(animal.padre) if animal.padre else 'No registrado',
        'compra_id': animal.compra_id, 'venta_id': animal.venta_id,
        'compra': str(animal.compra) if animal.compra else 'Sin compra asociada',
        'foto_url': animal.foto.url if animal.foto else '',
        'venta': str(animal.venta) if animal.venta else 'Sin venta asociada',
    }


def _movimientos_data():
    return [{
        'fecha': m.fecha.isoformat(), 'hora': '', 'tipo': m.tipo,
        'caravana': str(m.animal.id_senasa), 'animal': m.animal.nombre,
        'categoria': _categoria(m.animal), 'cantidad': 1,
        'origen': str(m.origen) if m.origen else '-', 'destino': str(m.destino) if m.destino else '-',
        'usuario': 'Sistema', 'obs': m.observaciones or '-', 'estado': 'Confirmado',
    } for m in MovimientoAnimal.objects.select_related('animal', 'origen', 'destino')]


def _page(request, template, data_key=None, data=None):
    # Fuerza la cookie CSRF para que las acciones AJAX de cada pantalla puedan
    # hacer POST sin desactivar la protección de Django.
    get_token(request)
    return render(request, template, {'page_data_key': data_key, 'page_data': data or {}})


def dashboard(request):
    movimientos = _movimientos_data()[:10]
    data = {'movimientos': [{**m, 'fecha': '/'.join(reversed(m['fecha'].split('-')))} for m in movimientos]}
    return _page(request, 'index.html', 'dashboard', data)


def stock(request):
    animales = Animal.objects.select_related('parcela', 'dieta', 'madre', 'padre', 'compra', 'venta').all()
    return _page(request, 'stock.html', 'stock', {
        'animales': [_animal_data(a) for a in animales],
        'parcelas': [{'id': p.id, 'nombre': str(p)} for p in Parcela.objects.select_related('establecimiento')],
        'dietas': [{'id': d.id, 'nombre': str(d)} for d in Dieta.objects.all()],
        'progenitores': [{'id': a.id, 'nombre': f'#{a.id_senasa if a.id_senasa is not None else "S/C"} — {a.nombre or "S/N"}', 'sexo': a.sexo} for a in animales],
        'compras': [{'id': c.id, 'nombre': str(c)} for c in Compra.objects.all()],
        'ventas': [{'id': v.id, 'nombre': str(v)} for v in Venta.objects.all()],
    })


def _to_iso_date(value):
    if value is None:
        return ''
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _normalizar_dni(valor):
    """Devuelve None cuando el DNI viene vacío para permitir personas sin DNI."""
    valor = (valor or '').strip()
    return valor or None


def _venta_data(venta):
    animales = list(venta.animal_set.all())
    return {
        'id': venta.id, 'tipo': venta.tipo, 'fecha': _to_iso_date(venta.fecha),
        'peso_total': str(venta.peso_total), 'precio_por_kg': str(venta.precio_por_kg),
        'monto_total': str(venta.monto_total), 'detalle': venta.detalle or '',
        'comprador_id': venta.comprador_id,
        'comprador': str(venta.comprador) if venta.comprador else 'Sin comprador',
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


def _movimientos_financieros_data():
    return [{
        'id': m.id,
        'fecha': m.fecha.isoformat(),
        'tipo': m.tipo,
        'nombre': m.nombre,
        'detalle': m.detalle or '',
        'monto_total': str(m.monto_total),
    } for m in MovimientoFinanciero.objects.order_by('-fecha', '-id')]


def finanzas(request):
    # Pantalla central de Finanzas: métricas, gráfico y listado CRUD de movimientos financieros.
    today = date.today()
    anio = today.year
    mes = today.month

    movimientos_mes = MovimientoFinanciero.objects.filter(fecha__year=anio, fecha__month=mes)
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
        qs = MovimientoFinanciero.objects.filter(fecha__year=y, fecha__month=m)
        ingresos_series.append(float(qs.filter(tipo='Ingreso').aggregate(total=Sum('monto_total'))['total'] or 0))
        egresos_series.append(float(qs.filter(tipo='Egreso').aggregate(total=Sum('monto_total'))['total'] or 0))

    import json
    return _page(request, 'finanzas.html', 'finanzas', {
        'kpis': {
            'total_movimientos_mes': kpi_total,
            'ingresos_mes': float(kpi_ingresos),
            'egresos_mes': float(kpi_egresos),
            'balance_mes': float(kpi_balance),
        },
        'movimientos': _movimientos_financieros_data()[:50],
        'chart': {
            'labels_json': json.dumps(meses),
            'ingresos_json': json.dumps(ingresos_series),
            'egresos_json': json.dumps(egresos_series),
        }
    })


def _parse_decimal(value):
    return Decimal(str(value)) if value is not None and str(value).strip() != '' else None


def finanzas_api_list_create(request):
    """GET: lista movimientos (JSON). POST: crear movimiento financiero."""
    if request.method == 'GET':
        return JsonResponse({'movimientos': _movimientos_financieros_data()})

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
            )
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
        return JsonResponse({'movimiento': {
            'id': movimiento.id, 'fecha': movimiento.fecha.isoformat(), 'tipo': movimiento.tipo,
            'nombre': movimiento.nombre, 'detalle': movimiento.detalle or '', 'monto_total': str(movimiento.monto_total),
        }}, status=201)


@require_POST
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
    }})


@require_POST
def eliminar_movimiento_financiero(request, movimiento_id):
    movimiento = get_object_or_404(MovimientoFinanciero, pk=movimiento_id)
    movimiento.delete()
    return JsonResponse({'ok': True})


def _sincronizar_costo_entidades(movimiento):
    """Mantiene el costo del movimiento sincronizado con la entidad asociada (venta, compra o evento sanitario)."""
    monto = movimiento.monto_total
    Venta.objects.filter(mov_financiero_id=movimiento.id).update(monto_total=monto)
    Compra.objects.filter(mov_financiero_id=movimiento.id).update(monto_total=monto)
    EventoSanitario.objects.filter(mov_financiero_id=movimiento.id).update(costo_total=monto)


def potreros(request):
    parcelas = Parcela.objects.select_related('establecimiento').prefetch_related('animal_set')
    datos, animales = [], {}
    for p in parcelas:
        nombre = _nombre_parcela(p)
        residentes = [_animal_data(a) for a in p.animal_set.filter(vivo=True, vendido=False)]
        animales[nombre] = residentes
        datos.append(_parcela_data(p, actual=len(residentes)))
    return _page(request, 'potreros.html', 'potreros', {'potreros': datos, 'animales_por_potrero': animales})


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
    return animal_ids


def _evento_sanitario_data(evento):
    detalles = []
    for detalle in evento.detalles.all():
        animal = detalle.animal
        detalles.append({
            'id': animal.id,
            'nombre': animal.nombre or 'S/N',
            'caravana': str(animal.id_senasa) if animal.id_senasa is not None else 'S/N',
            'categoria': _categoria(animal),
            'edad': _edad(animal),
            'potrero': str(animal.parcela) if animal.parcela else 'Sin asignar',
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
        'potrero': detalles[0]['potrero'] if detalles else 'Sin asignar',
        'veterinario_id': evento.veterinario_id,
        'veterinario': str(evento.veterinario) if evento.veterinario else '-',
        'diagnostico_id': evento.diagnostico_id,
        'diagnostico': str(evento.diagnostico) if evento.diagnostico else '-',
        'lote_id': evento.lote_id if hasattr(evento, 'lote_id') else None,
        'lote': str(evento.lote) if hasattr(evento, 'lote') and evento.lote else '-',
        'lote_insumo_id': evento.lote.insumo_id if evento.lote and evento.lote.insumo_id else None,
        'lote_insumo_tipo': evento.lote.insumo.tipo if evento.lote and evento.lote.insumo else None,
        'cantidad': str(getattr(evento, 'cantidad', '') or ''),
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
    if diagnostico.animal_id != animal_anterior.id:
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
    veterinario = get_object_or_404(Veterinario, pk=veterinario_id)
    try:
        _asignar_veterinario(veterinario, request.POST)
        veterinario.full_clean()
        veterinario.save()
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'veterinario': _veterinario_data(veterinario)})


@require_POST
def eliminar_veterinario(request, veterinario_id):
    veterinario = get_object_or_404(Veterinario, pk=veterinario_id)
    veterinario.delete()
    return JsonResponse({'ok': True})


def _recalcular_estado_enfermo(animal):
    animal.enfermo = Diagnostico.objects.filter(animal=animal).exclude(estado_actual='Curado').exists()
    animal.save(update_fields=['enfermo'])


def sanidad(request):
    today = date.today()
    eventos = EventoSanitario.objects.select_related('veterinario', 'diagnostico', 'lote').prefetch_related('detalles__animal__parcela').order_by('-fecha_aplicacion', '-id')
    eventos_aplicados_mes = EventoSanitario.objects.filter(
        estado=True,
        fecha_aplicacion__year=today.year, fecha_aplicacion__month=today.month,
    ).count()
    proximas_aplicaciones = EventoSanitario.objects.filter(
        estado=False, fecha_aplicacion__gte=today,
    ).count()
    animales_enfermos = Animal.objects.filter(enfermo=True).count()
    enfermedades = Enfermedad.objects.order_by('nombre')
    diagnosticos = Diagnostico.objects.select_related('animal', 'enfermedad').order_by('-fecha_deteccion')
    veterinarios = Veterinario.objects.order_by('apellido', 'nombre')
    lotes = Lote.objects.select_related('insumo').order_by('insumo__nombre', 'fechaVencimiento')
    # Incluir animales vivos aunque ya hayan sido vendidos para permitir registrar eventos y diagnósticos históricos.
    animales = Animal.objects.filter(vivo=True).select_related('parcela').order_by('id_senasa')

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
        'insumos': [_insumo_data(i) for i in Insumo.objects.order_by('nombre')],
        'tipos_evento': [choice[0] for choice in EventoSanitario.TIPO_CHOICES],
        'animales': [{
            'id': a.id,
            'nombre': a.nombre or 'S/N',
            'caravana': str(a.id_senasa) if a.id_senasa is not None else 'S/N',
            'sexo': a.sexo,
            'tipo_animal': a.tipo_animal,
            'categoria': _categoria(a),
            'potrero': str(a.parcela) if a.parcela else 'Sin asignar',
            'enfermo': a.enfermo,
        } for a in animales],
    }
    return _page(request, 'sanidad.html', 'sanidad', data)


@require_POST
def crear_evento_sanitario(request):
    try:
        evento = EventoSanitario()
        animal_ids = _asignar_evento_sanitario(evento, request.POST)
        evento.full_clean()
        with transaction.atomic():
            evento.save()
            evento.detalles.all().delete()
            for animal_id in animal_ids:
                DetalleEvento.objects.create(evento=evento, animal_id=animal_id)
            _sync_movimiento_evento(evento)
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'evento': _evento_sanitario_data(evento)}, status=201)


@require_POST
def actualizar_evento_sanitario(request, evento_id):
    evento = get_object_or_404(EventoSanitario, pk=evento_id)
    try:
        animal_ids = _asignar_evento_sanitario(evento, request.POST)
        evento.full_clean()
        with transaction.atomic():
            evento.save()
            evento.detalles.all().delete()
            for animal_id in animal_ids:
                DetalleEvento.objects.create(evento=evento, animal_id=animal_id)
            _sync_movimiento_evento(evento)
    except (KeyError, ValueError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'evento': _evento_sanitario_data(evento)})


def _sync_movimiento_evento(evento):
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
            },
        )
        if evento.mov_financiero_id != movimiento.id:
            EventoSanitario.objects.filter(pk=evento.pk).update(mov_financiero=movimiento)
    elif evento.mov_financiero_id:
        MovimientoFinanciero.objects.filter(pk=evento.mov_financiero_id).delete()
        EventoSanitario.objects.filter(pk=evento.pk).update(mov_financiero=None)


@require_POST
def eliminar_evento_sanitario(request, evento_id):
    evento = get_object_or_404(EventoSanitario, pk=evento_id)
    movimiento_id = evento.mov_financiero_id
    evento.delete()
    if movimiento_id:
        MovimientoFinanciero.objects.filter(pk=movimiento_id).delete()
    return JsonResponse({'ok': True})


def vacunacion(request):
    return sanidad(request)


def pesajes(request):
    animales = list(Animal.objects.select_related('parcela').all())
    historial = {str(a.id_senasa): [{'fecha': p.fecha.strftime('%d/%m/%Y'), 'peso': float(p.peso)} for p in a.pesajes.all()] for a in animales}
    data = {'animales_pesaje': [_animal_data(a) | {'responsable': 'Sistema'} for a in animales], 'historial': historial}
    return _page(request, 'pesajes.html', 'pesajes', data)


def alimentacion(request):
    hoy = date.today()
    periodo_inicio = hoy - timedelta(days=30)

    alimentos_qs = (
        Insumo.objects.filter(tipo='Alimento')
        .prefetch_related('lotes__detalles_compra', 'lotes__consumos__evento_sanitario')
    )

    alimentos = []
    for insumo in alimentos_qs:
        lotes = list(insumo.lotes.all())
        stock_total = sum((lote.stockActual or Decimal('0')) for lote in lotes)

        detalles_compra = [detalle for lote in lotes for detalle in lote.detalles_compra.all()]
        ultima_compra = '-'
        precio_unitario = Decimal('0')
        if detalles_compra:
            detalles_ordenados = sorted(
                detalles_compra,
                key=lambda d: d.compra.fecha if d.compra and d.compra.fecha is not None else date.min,
                reverse=True,
            )
            detalle_reciente = detalles_ordenados[0]
            if detalle_reciente.precioUnitario is not None:
                precio_unitario = detalle_reciente.precioUnitario
            if detalle_reciente.compra and detalle_reciente.compra.fecha:
                ultima_compra = detalle_reciente.compra.fecha.strftime('%d/%m/%Y')

        consumo_mensual = Decimal('0')
        for lote in lotes:
            for consumo in lote.consumos.all():
                fecha_evento = getattr(consumo.evento_sanitario, 'fecha_aplicacion', None)
                if fecha_evento and fecha_evento >= periodo_inicio:
                    consumo_mensual += consumo.cantidad or Decimal('0')

        alimentos.append({
            'id': str(insumo.id),
            'nombre': insumo.nombre or f'Insumo {insumo.id}',
            'categoria': insumo.tipo or 'Alimento',
            'stock': float(stock_total),
            'unidad': insumo.unidadDeMedida or '',
            'consumoMensual': float(consumo_mensual),
            'stockMinimo': float(insumo.stockMinimo or Decimal('0')),
            'ultimaCompra': ultima_compra,
            'precioUnitario': float(precio_unitario),
        })

    return _page(request, 'alimentacion.html', 'alimentacion', {'alimentos': alimentos})


def usuarios(request):
    roles = {r.usuario_id: r for r in RolEstablecimiento.objects.select_related('usuario__persona')}
    data = {'usuarios': [{
        'id': u.id, 'nombre': u.persona.nombre, 'apellido': u.persona.apellido,
        'usuario': u.nombre_usuario, 'email': u.persona.correo_electronico,
        'telefono': '', 'cargo': '', 'rol': roles[u.id].nombre if u.id in roles else 'Operario',
        'estado': 'Activo' if u.id in roles and roles[u.id].estado_acceso else 'Inactivo',
        'creado': roles[u.id].fecha_ingreso.isoformat() if u.id in roles else date.today().isoformat(),
        'acceso': date.today().isoformat() + 'T00:00', 'conectado': False,
    } for u in Usuario.objects.select_related('persona')]}
    return _page(request, 'usuarios.html', 'usuarios', data)


def configuracion(request):
    return _page(request, 'configuracion.html')


def stock_api(request):
    return JsonResponse({'animales': [_animal_data(a) for a in Animal.objects.select_related('parcela', 'dieta', 'madre', 'padre', 'compra', 'venta')]})


def _asignar_campos_animal(animal, datos, es_alta=False):
    """Centraliza la asignación para que el alta y la edición tengan las mismas reglas."""
    valor_senasa = datos.get('id_senasa', '').strip()
    animal.id_senasa = int(valor_senasa) if valor_senasa else None
    animal.nombre = datos.get('nombre', '').strip()
    animal.tipo_animal = datos['tipo_animal']
    animal.sexo = datos['sexo']
    animal.raza = datos.get('raza', '').strip() or None
    animal.fecha_nacimiento = datos.get('fecha_nacimiento') or None
    for campo in ('peso_al_nacer', 'peso_al_destete', 'peso_actual', 'costo_adquisicion', 'precio_venta', 'diametro_escrotal'):
        setattr(animal, campo, datos.get(campo) or None)
    animal.vendido = datos.get('vendido') == 'on'
    animal.vivo = datos.get('vivo') == 'on' if 'vivo' in datos else es_alta
    animal.enfermo = datos.get('enfermo') == 'on'
    animal.castrado = datos.get('castrado') == 'on'
    animal.color = datos.get('color', '').strip() or None
    animal.parcela_id = datos.get('parcela_id') or None
    animal.dieta_id = datos.get('dieta_id') or None
    animal.madre_id = datos.get('madre_id') or None
    animal.padre_id = datos.get('padre_id') or None
    animal.compra_id = datos.get('compra_id') or None
    animal.venta_id = datos.get('venta_id') or None
    animal.descripcion = datos.get('descripcion', '').strip() or None
    if animal.sexo != 'Macho':
        animal.diametro_escrotal = None
    if animal.pk and animal.pk in (animal.madre_id, animal.padre_id):
        raise ValueError('Un animal no puede ser su propio progenitor.')
    if animal.madre_id and animal.madre.sexo != 'Hembra':
        raise ValueError('La madre seleccionada debe ser hembra.')
    if animal.padre_id and animal.padre.sexo != 'Macho':
        raise ValueError('El padre seleccionado debe ser macho.')


@require_POST
def crear_animal(request):
    try:
        animal = Animal()
        _asignar_campos_animal(animal, request.POST, es_alta=True)
        if 'foto' in request.FILES and request.FILES['foto']:
            animal.foto = request.FILES['foto']
        animal.full_clean()
        animal.save()
    except (KeyError, ValueError, ValidationError):
        return JsonResponse({'error': 'Completá correctamente los campos obligatorios.'}, status=400)
    except IntegrityError:
        return JsonResponse({'error': 'La caravana SENASA ya se encuentra registrada.'}, status=400)

    MovimientoAnimal.objects.create(
        animal=animal, fecha=date.today(), tipo='Alta', destino=animal.parcela,
        observaciones='Alta inicial del animal en el sistema.',
    )
    return JsonResponse({'id': animal.id, 'animal': _animal_data(animal)}, status=201)


@require_POST
def actualizar_animal(request, animal_id):
    animal = get_object_or_404(Animal, pk=animal_id)
    try:
        _asignar_campos_animal(animal, request.POST)
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
    animal = get_object_or_404(Animal, pk=animal_id)
    animal.delete()
    return JsonResponse({'ok': True})


@require_POST
def crear_potrero(request):
    es_edicion = bool(request.POST.get('id'))
    parcela = None
    try:
        if es_edicion:
            parcela = get_object_or_404(Parcela, pk=request.POST['id'])
        else:
            parcela = Parcela()

        establecimiento_id = request.POST.get('establecimiento_id')
        if not establecimiento_id:
            from establecimientos.models import Establecimiento
            establecimiento = Establecimiento.objects.order_by('id').first()
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
        return JsonResponse({'error': 'Completá correctamente el ancho y largo del potrero.'}, status=400)
    return JsonResponse({'id': parcela.id, 'parcela': _parcela_data(parcela)}, status=200 if es_edicion else 201)


@require_POST
def eliminar_potrero(request, parcela_id):
    parcela = get_object_or_404(Parcela, pk=parcela_id)
    parcela.delete()
    return JsonResponse({'ok': True})


@require_POST
def crear_pesaje(request):
    animal = get_object_or_404(Animal, pk=request.POST.get('animal_id'))
    peso = Decimal(request.POST['peso'])
    pesaje = Pesaje.objects.create(animal=animal, fecha=request.POST.get('fecha') or date.today(), peso=peso,
                                   observaciones=request.POST.get('observaciones', ''))
    animal.peso_actual = peso
    animal.save(update_fields=['peso_actual'])
    return JsonResponse({'id': pesaje.id, 'animal_id': animal.id, 'peso': str(pesaje.peso)})


@require_POST
def crear_movimiento(request):
    animal = get_object_or_404(Animal, pk=request.POST.get('animal_id'))
    movimiento = MovimientoAnimal.objects.create(
        animal=animal, fecha=request.POST.get('fecha') or date.today(), tipo=request.POST['tipo'],
        origen_id=request.POST.get('origen_id') or None, destino_id=request.POST.get('destino_id') or None,
        observaciones=request.POST.get('observaciones', ''),
    )
    if movimiento.destino_id:
        animal.parcela_id = movimiento.destino_id
        animal.save(update_fields=['parcela'])
    return JsonResponse({'id': movimiento.id})


def _registrar_venta(venta, datos):
    """Guarda una venta y todos sus efectos como una única transacción."""
    try:
        precio_por_kg = Decimal(datos['precio_por_kg'])
        animales_ids = [int(animal_id) for animal_id in datos.getlist('animales')]
    except (KeyError, ValueError, ArithmeticError):
        raise ValueError('Indicá un precio por kilo válido y al menos un animal.')
    if precio_por_kg <= 0 or not animales_ids or len(animales_ids) != len(set(animales_ids)):
        raise ValueError('Indicá un precio por kilo válido y al menos un animal.')

    animales = list(Animal.objects.select_for_update().filter(pk__in=animales_ids, vivo=True, vendido=False))
    if len(animales) != len(animales_ids):
        raise ValueError('Uno o más animales ya no están disponibles para la venta.')

    peso_total_manual = _parse_decimal(datos.get('peso_total'))
    peso_manual = str(datos.get('peso_manual', '')).lower() in {'1', 'true', 'on', 'yes'}
    if peso_total_manual is None:
        if any(animal.peso_actual is None or animal.peso_actual <= 0 for animal in animales):
            raise ValueError('Todos los animales seleccionados deben tener un peso actual mayor a cero o indicar un peso total manual.')
        peso_total = sum((animal.peso_actual for animal in animales), Decimal('0'))
    else:
        peso_total = peso_total_manual

    monto_total = (peso_total * precio_por_kg).quantize(Decimal('0.01'))
    venta.tipo = datos.get('tipo', 'Venta de animales').strip() or 'Venta de animales'
    venta.fecha = datos.get('fecha') or date.today()
    venta.comprador_id = datos.get('comprador_id') or None
    venta.detalle = datos.get('detalle', '').strip() or None
    venta.peso_total = peso_total
    venta.precio_por_kg = precio_por_kg
    venta.monto_total = monto_total
    venta.full_clean()
    venta.save()

    movimiento, _ = MovimientoFinanciero.objects.update_or_create(
        pk=venta.mov_financiero_id,
        defaults={
            'tipo': 'Ingreso', 'nombre': f'Venta #{venta.id}', 'monto_total': monto_total,
            'fecha': venta.fecha, 'detalle': venta.detalle or f'Venta de {len(animales)} animal(es).',
        },
    )
    if venta.mov_financiero_id != movimiento.id:
        venta.mov_financiero = movimiento
        venta.save(update_fields=['mov_financiero'])

    for animal in animales:
        if peso_manual:
            precio_venta_animal = ((peso_total / len(animales)) * precio_por_kg).quantize(Decimal('0.01'))
        else:
            precio_venta_animal = ((animal.peso_actual or Decimal('0')) * precio_por_kg).quantize(Decimal('0.01'))
        animal.vendido = True
        animal.venta = venta
        animal.precio_venta = precio_venta_animal
        animal.save(update_fields=['vendido', 'venta', 'precio_venta'])
        MovimientoAnimal.objects.create(
            animal=animal, fecha=venta.fecha, tipo='Venta', origen=animal.parcela,
            observaciones=f'Venta #{venta.id}.',
        )


def _revertir_venta(venta):
    """Deshace los efectos sobre animales para poder editar o eliminar una venta."""
    animales = Animal.objects.select_for_update().filter(venta=venta)
    animales.update(vendido=False, venta=None, precio_venta=None)
    MovimientoAnimal.objects.filter(animal__in=animales, tipo='Venta', fecha=venta.fecha,
                                    observaciones=f'Venta #{venta.id}.').delete()


@require_POST
def crear_comprador(request):
    try:
        comprador = Comprador.objects.create(
            dni=_normalizar_dni(request.POST.get('dni', '')),
            nombre=request.POST['nombre'].strip(),
            apellido=request.POST['apellido'].strip(),
            correo_electronico=request.POST['correo_electronico'],
            fecha_nacimiento=request.POST['fecha_nacimiento'],
            telefono=request.POST.get('telefono', '').strip(),
        )
    except (KeyError, ValueError, ValidationError, IntegrityError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo crear el comprador.'}, status=400)
    return JsonResponse({'id': comprador.id, 'comprador': _comprador_data(comprador)}, status=201)


@require_POST
def actualizar_comprador(request, comprador_id):
    comprador = get_object_or_404(Comprador, pk=comprador_id)
    try:
        comprador.dni = _normalizar_dni(request.POST.get('dni', comprador.dni))
        comprador.nombre = request.POST.get('nombre', comprador.nombre).strip()
        comprador.apellido = request.POST.get('apellido', comprador.apellido).strip()
        comprador.correo_electronico = request.POST.get('correo_electronico', comprador.correo_electronico)
        comprador.fecha_nacimiento = request.POST.get('fecha_nacimiento', comprador.fecha_nacimiento)
        comprador.telefono = request.POST.get('telefono', comprador.telefono or '').strip()
        comprador.full_clean()
        comprador.save()
    except (ValueError, ValidationError, IntegrityError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo actualizar el comprador.'}, status=400)
    return JsonResponse({'comprador': _comprador_data(comprador)})


@require_POST
def eliminar_comprador(request, comprador_id):
    comprador = get_object_or_404(Comprador, pk=comprador_id)
    comprador.delete()
    return JsonResponse({'ok': True})


@require_POST
def crear_venta(request):
    try:
        with transaction.atomic():
            venta = Venta()
            _registrar_venta(venta, request.POST)
    except (ValueError, ValidationError, IntegrityError, ArithmeticError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo registrar la venta.'}, status=400)
    return JsonResponse({'id': venta.id, 'venta': _venta_data(venta)}, status=201)


@require_POST
def actualizar_venta(request, venta_id):
    try:
        with transaction.atomic():
            venta = get_object_or_404(Venta.objects.select_for_update(), pk=venta_id)
            _revertir_venta(venta)
            _registrar_venta(venta, request.POST)
    except (ValueError, ValidationError, IntegrityError, ArithmeticError) as error:
        return JsonResponse({'error': str(error) or 'No se pudo actualizar la venta.'}, status=400)
    return JsonResponse({'venta': _venta_data(venta)})


@require_POST
def eliminar_venta(request, venta_id):
    with transaction.atomic():
        venta = get_object_or_404(Venta.objects.select_for_update(), pk=venta_id)
        movimiento_id = venta.mov_financiero_id
        _revertir_venta(venta)
        venta.delete()
        if movimiento_id:
            MovimientoFinanciero.objects.filter(pk=movimiento_id).delete()
    return JsonResponse({'ok': True})
