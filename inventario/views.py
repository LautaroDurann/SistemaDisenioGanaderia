from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from inventario.models import Insumo, Lote


def _parse_fecha(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    if hasattr(value, 'date'):
        return value.date()
    return date.fromisoformat(str(value))


def _serialize_insumo(insumo, include_lotes=False):
    total_stock = insumo.lotes.aggregate(total=Sum('stockActual'))['total'] or Decimal('0')
    cantidad_total = total_stock.quantize(Decimal('0.00'))
    result = {
        'id': insumo.id,
        'nombre': insumo.nombre,
        'tipo': insumo.tipo,
        'unidad_de_medida': insumo.unidadDeMedida,
        'stock_minimo': str(insumo.stockMinimo) if insumo.stockMinimo is not None else '0',
        'cantidad_total': str(cantidad_total),
    }
    if include_lotes:
        result['lotes'] = [
            {
                'id': lote.id,
                'nombre': lote.nombre,
                'fecha_vencimiento': lote.fechaVencimiento.isoformat() if lote.fechaVencimiento else '',
                'stock_actual': str(lote.stockActual) if lote.stockActual is not None else '0',
            }
            for lote in insumo.lotes.order_by('fechaVencimiento', 'id')
        ]
    return result


def _serialize_lote(lote):
    return {
        'id': lote.id,
        'nombre': lote.nombre,
        'fecha_vencimiento': lote.fechaVencimiento.isoformat() if lote.fechaVencimiento else '',
        'stock_actual': str(lote.stockActual) if lote.stockActual is not None else '0',
        'insumo_id': lote.insumo_id,
    }


@require_http_methods(['GET', 'POST'])
def insumo_lotes(request, insumo_id):
    insumo = get_object_or_404(Insumo, pk=insumo_id)

    if request.method == 'GET':
        return JsonResponse({'lotes': [_serialize_lote(lote) for lote in insumo.lotes.order_by('fechaVencimiento', 'id')]})

    try:
        nombre = request.POST.get('nombre', '').strip() or None
        fecha_vencimiento = _parse_fecha(request.POST.get('fecha_vencimiento', '').strip())
        stock_raw = request.POST.get('stock_actual', '').strip() or '0'
        stock_actual = Decimal(stock_raw)
        lote = Lote.objects.create(
            insumo=insumo,
            nombre=nombre,
            fechaVencimiento=fecha_vencimiento,
            stockActual=stock_actual,
        )
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    return JsonResponse({'lote': _serialize_lote(lote)}, status=201)


@require_http_methods(['GET', 'POST', 'DELETE'])
def lote_detalle(request, lote_id):
    lote = get_object_or_404(Lote, pk=lote_id)

    if request.method == 'GET':
        return JsonResponse({'lote': _serialize_lote(lote)})

    if request.method == 'POST':
        try:
            lote.nombre = request.POST.get('nombre', lote.nombre).strip() or lote.nombre
            lote.fechaVencimiento = _parse_fecha(request.POST.get('fecha_vencimiento', lote.fechaVencimiento))
            stock_raw = request.POST.get('stock_actual', '').strip()
            if stock_raw != '':
                lote.stockActual = Decimal(stock_raw)
            lote.save()
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        return JsonResponse({'lote': _serialize_lote(lote)})

    lote.delete()
    return JsonResponse({'ok': True})


def insumos(request):
    insumos_qs = Insumo.objects.prefetch_related('lotes').annotate(cantidad_total=Sum('lotes__stockActual')).all()
    total_insumos = insumos_qs.count()
    vacunas = insumos_qs.filter(tipo='Vacuna').count()
    medicamentos = insumos_qs.filter(tipo='Medicamento').count()
    alimentos = insumos_qs.filter(tipo='Alimento').count()
    stock_total = sum((lote.stockActual or Decimal('0')) for insumo in insumos_qs for lote in insumo.lotes.all())

    return render(request, 'insumos.html', {
        'insumos': [
            {
                'id': insumo.id,
                'nombre': insumo.nombre,
                'tipo': insumo.tipo,
                'unidad_de_medida': insumo.unidadDeMedida,
                'cantidad_total': str((insumo.cantidad_total or Decimal('0')).quantize(Decimal('0.00'))),
            }
            for insumo in insumos_qs
        ],
        'stats': {
            'total_insumos': total_insumos,
            'vacunas': vacunas,
            'medicamentos': medicamentos,
            'alimentos': alimentos,
            'stock_total': float(stock_total),
        },
    })


@require_http_methods(['GET', 'POST'])
def insumos_api(request):
    if request.method == 'GET':
        query = request.GET.get('q', '').strip()
        tipo = request.GET.get('tipo', '').strip()
        qs = Insumo.objects.all()
        if query:
            qs = qs.filter(Q(nombre__icontains=query) | Q(tipo__icontains=query))
        if tipo:
            qs = qs.filter(tipo=tipo)

        data = [_serialize_insumo(insumo) for insumo in qs]
        return JsonResponse({'insumos': data})

    if request.method == 'POST':
        try:
            stock_minimo = request.POST.get('stockMinimo', request.POST.get('stock_minimo', '')).strip()
            insumo = Insumo.objects.create(
                nombre=request.POST.get('nombre', '').strip(),
                tipo=request.POST.get('tipo', 'Otros').strip() or 'Otros',
                unidadDeMedida=request.POST.get('unidadDeMedida', request.POST.get('unidad_de_medida', 'kg')).strip() or 'kg',
                stockMinimo=Decimal(stock_minimo) if stock_minimo else None,
            )
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        return JsonResponse({'insumo': _serialize_insumo(insumo)}, status=201)


@require_http_methods(['GET', 'POST', 'DELETE'])
def insumo_detalle(request, insumo_id):
    insumo = get_object_or_404(Insumo, pk=insumo_id)

    if request.method == 'GET':
        return JsonResponse({'insumo': _serialize_insumo(insumo, include_lotes=True)})

    if request.method == 'POST':
        try:
            insumo.nombre = request.POST.get('nombre', insumo.nombre).strip()
            insumo.tipo = request.POST.get('tipo', insumo.tipo).strip() or insumo.tipo
            insumo.unidadDeMedida = request.POST.get('unidadDeMedida', request.POST.get('unidad_de_medida', insumo.unidadDeMedida)).strip() or insumo.unidadDeMedida
            stock_minimo = request.POST.get('stockMinimo', request.POST.get('stock_minimo', '')).strip()
            if stock_minimo != '':
                insumo.stockMinimo = Decimal(stock_minimo)
            insumo.save()
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        return JsonResponse({'insumo': _serialize_insumo(insumo, include_lotes=True)})

    if request.method == 'DELETE':
        insumo.delete()
        return JsonResponse({'ok': True})
