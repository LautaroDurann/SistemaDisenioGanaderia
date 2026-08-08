from datetime import date
from decimal import Decimal

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from inventario.models import Insumo, Lote
from web.views import _establecimiento_actual


def _parse_fecha(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    if hasattr(value, 'date'):
        return value.date()
    return date.fromisoformat(str(value))


def _lotes_de(insumo, establecimiento):
    lotes = insumo.lotes.all()
    if establecimiento is not None:
        lotes = lotes.filter(establecimiento=establecimiento)
    return lotes


def _serialize_insumo(insumo, include_lotes=False, establecimiento=None):
    lotes = list(_lotes_de(insumo, establecimiento))
    total_stock = sum((lote.stockActual or Decimal('0')) for lote in lotes) + Decimal('0')
    cantidad_total = total_stock.quantize(Decimal('0.00'))
    result = {
        'id': insumo.id,
        'nombre': insumo.nombre,
        'tipo': insumo.tipo,
        'unidad_de_medida': insumo.unidadDeMedida,
        'cantidad_total': str(cantidad_total),
        'establecimiento_id': establecimiento.id if establecimiento else None,
    }
    if include_lotes:
        result['lotes'] = [
            {
                'id': lote.id,
                'nombre': lote.nombre,
                'fecha_vencimiento': lote.fechaVencimiento.isoformat() if lote.fechaVencimiento else '',
                'stock_actual': str(lote.stockActual) if lote.stockActual is not None else '0',
                'establecimiento': lote.establecimiento.nombre if lote.establecimiento else '',
            }
            for lote in sorted(lotes, key=lambda l: (l.fechaVencimiento or date.max, l.id))
        ]
    return result


def _serialize_lote(lote):
    return {
        'id': lote.id,
        'nombre': lote.nombre,
        'fecha_vencimiento': lote.fechaVencimiento.isoformat() if lote.fechaVencimiento else '',
        'stock_actual': str(lote.stockActual) if lote.stockActual is not None else '0',
        'insumo_id': lote.insumo_id,
        'establecimiento_id': lote.establecimiento_id,
        'establecimiento': lote.establecimiento.nombre if lote.establecimiento else '',
    }


@require_http_methods(['GET', 'POST'])
def insumo_lotes(request, insumo_id):
    insumo = get_object_or_404(Insumo, pk=insumo_id)
    establecimiento = _establecimiento_actual(request)

    if request.method == 'GET':
        lotes = _lotes_de(insumo, establecimiento).order_by('fechaVencimiento', 'id')
        return JsonResponse({'lotes': [_serialize_lote(lote) for lote in lotes]})

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
            establecimiento=establecimiento,
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


@ensure_csrf_cookie
def insumos(request):
    establecimiento = _establecimiento_actual(request)

    lotes = Lote.objects.select_related('insumo').all()
    if establecimiento is not None:
        lotes = lotes.filter(establecimiento=establecimiento)
    stock_por_insumo = {}
    for lote in lotes:
        if lote.insumo_id is None:
            continue
        stock_por_insumo[lote.insumo_id] = stock_por_insumo.get(lote.insumo_id, Decimal('0')) + (lote.stockActual or Decimal('0'))

    insumos_qs = Insumo.objects.order_by('nombre')
    insumos_list = []
    for insumo in insumos_qs:
        total = stock_por_insumo.get(insumo.id, Decimal('0')).quantize(Decimal('0.00'))
        insumos_list.append({
            'id': insumo.id,
            'nombre': insumo.nombre,
            'tipo': insumo.tipo,
            'unidad_de_medida': insumo.unidadDeMedida,
            'cantidad_total': str(total),
        })

    total_insumos = len(insumos_list)
    vacunas = sum(1 for i in insumos_list if i['tipo'] == 'Vacuna')
    medicamentos = sum(1 for i in insumos_list if i['tipo'] == 'Medicamento')
    alimentos = sum(1 for i in insumos_list if i['tipo'] == 'Alimento')
    stock_total = sum(stock_por_insumo.values())

    return render(request, 'insumos.html', {
        'insumos': insumos_list,
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
        establecimiento = _establecimiento_actual(request)
        qs = Insumo.objects.all()
        if query:
            qs = qs.filter(Q(nombre__icontains=query) | Q(tipo__icontains=query))
        if tipo:
            qs = qs.filter(tipo=tipo)

        data = [_serialize_insumo(insumo, establecimiento=establecimiento) for insumo in qs]
        return JsonResponse({'insumos': data})

    if request.method == 'POST':
        try:
            insumo = Insumo.objects.create(
                nombre=request.POST.get('nombre', '').strip(),
                tipo=request.POST.get('tipo', 'Otros').strip() or 'Otros',
                unidadDeMedida=request.POST.get('unidadDeMedida', request.POST.get('unidad_de_medida', 'kg')).strip() or 'kg',
            )
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        return JsonResponse({'insumo': _serialize_insumo(insumo)}, status=201)


@require_http_methods(['GET', 'POST', 'DELETE'])
def insumo_detalle(request, insumo_id):
    insumo = get_object_or_404(Insumo, pk=insumo_id)
    establecimiento = _establecimiento_actual(request)

    if request.method == 'GET':
        return JsonResponse({'insumo': _serialize_insumo(insumo, include_lotes=True, establecimiento=establecimiento)})

    if request.method == 'POST':
        try:
            insumo.nombre = request.POST.get('nombre', insumo.nombre).strip()
            insumo.tipo = request.POST.get('tipo', insumo.tipo).strip() or insumo.tipo
            insumo.unidadDeMedida = request.POST.get('unidadDeMedida', request.POST.get('unidad_de_medida', insumo.unidadDeMedida)).strip() or insumo.unidadDeMedida
            insumo.save()
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        return JsonResponse({'insumo': _serialize_insumo(insumo, include_lotes=True, establecimiento=establecimiento)})

    if request.method == 'DELETE':
        insumo.delete()
        return JsonResponse({'ok': True})
