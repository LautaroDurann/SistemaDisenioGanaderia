import calendar
from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, Sum
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
from inventario.models import Dieta, Insumo
from sanidad.models import EventoSanitario
from usuarios.models import Comprador, RolEstablecimiento, Usuario


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


def _venta_data(venta):
    animales = list(venta.animal_set.all())
    return {
        'id': venta.id, 'tipo': venta.tipo, 'fecha': venta.fecha.isoformat(),
        'peso_total': str(venta.peso_total), 'precio_por_kg': str(venta.precio_por_kg),
        'monto_total': str(venta.monto_total), 'detalle': venta.detalle or '',
        'comprador_id': venta.comprador_id,
        'comprador': str(venta.comprador) if venta.comprador else 'Sin comprador',
        'animales': [_animal_data(a) for a in animales],
    }


def _movimientos_financieros_data():
    return [{
        'id': m.id, 'fecha': m.fecha.isoformat(), 'tipo': m.tipo, 'nombre': m.nombre,
        'detalle': m.detalle or '', 'monto_total': str(m.monto_total),
    } for m in MovimientoFinanciero.objects.order_by('-fecha', '-id')]


def finanzas(request):
    return _page(request, 'finanzas.html', 'finanzas', {
        'movimientos': _movimientos_financieros_data(),
    })


def ventas(request):
    animales = Animal.objects.filter(vivo=True, vendido=False).select_related('parcela')
    ventas_registradas = Venta.objects.select_related('comprador').prefetch_related('animal_set').order_by('-fecha', '-id')
    return _page(request, 'ventas.html', 'ventas', {
        'animales': [_animal_data(a) for a in animales],
        'ventas': [_venta_data(v) for v in ventas_registradas],
        'compradores': [{'id': c.id, 'nombre': str(c)} for c in Comprador.objects.all()],
    })


def compras(request):
    compras_registradas = Compra.objects.select_related('proveedor').order_by('-fecha', '-id')
    return _page(request, 'compras.html', 'compras', {'compras': [{
        'id': c.id, 'tipo': c.tipo, 'fecha': c.fecha.isoformat(), 'monto_total': str(c.monto_total),
        'proveedor': str(c.proveedor) if c.proveedor else 'Sin proveedor', 'detalle': c.detalle or '',
    } for c in compras_registradas]})


def potreros(request):
    parcelas = Parcela.objects.select_related('establecimiento').prefetch_related('animal_set')
    datos, animales = [], {}
    for p in parcelas:
        nombre = _nombre_parcela(p)
        residentes = [_animal_data(a) for a in p.animal_set.filter(vivo=True, vendido=False)]
        animales[nombre] = residentes
        datos.append(_parcela_data(p, actual=len(residentes)))
    return _page(request, 'potreros.html', 'potreros', {'potreros': datos, 'animales_por_potrero': animales})


def vacunacion(request):
    eventos = EventoSanitario.objects.filter(tipo='Vacunación').select_related('animal', 'veterinario')
    data = {'vacunaciones': [{
        'fecha': e.fecha_aplicacion.isoformat(), 'caravana': str(e.animal.id_senasa), 'animal': e.animal.nombre,
        'categoria': _categoria(e.animal), 'edad': _edad(e.animal),
        'potrero': str(e.animal.parcela) if e.animal.parcela else 'Sin asignar',
        'vacuna': e.detalle or 'Vacunación', 'proxima': '-',
        'veterinario': str(e.veterinario) if e.veterinario else '-',
        'estado': 'Vacunado' if e.estado else 'Pendiente', 'obs': e.detalle or '-',
    } for e in eventos]}
    return _page(request, 'vacunacion.html', 'vacunacion', data)


def pesajes(request):
    animales = list(Animal.objects.select_related('parcela').all())
    historial = {str(a.id_senasa): [{'fecha': p.fecha.strftime('%d/%m/%Y'), 'peso': float(p.peso)} for p in a.pesajes.all()] for a in animales}
    data = {'animales_pesaje': [_animal_data(a) | {'responsable': 'Sistema'} for a in animales], 'historial': historial}
    return _page(request, 'pesajes.html', 'pesajes', data)


def alimentacion(request):
    data = {'alimentos': [{'id': str(i.id), 'nombre': i.nombre, 'categoria': 'Insumo',
                           'stock': float(i.stock_actual), 'unidad': i.unidad_de_medida,
                           'consumoMensual': 0, 'stockMinimo': 0, 'ultimaCompra': '-', 'precioUnitario': 0}
                          for i in Insumo.objects.all()]}
    return _page(request, 'alimentacion.html', 'alimentacion', data)


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
    if any(animal.peso_actual is None or animal.peso_actual <= 0 for animal in animales):
        raise ValueError('Todos los animales seleccionados deben tener un peso actual mayor a cero.')

    peso_total = sum((animal.peso_actual for animal in animales), Decimal('0'))
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

    precio_promedio = monto_total / len(animales)
    for animal in animales:
        animal.vendido = True
        animal.venta = venta
        animal.precio_venta = precio_promedio
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
