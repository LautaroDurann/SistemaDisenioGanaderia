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


def _serialize_insumo(insumo):
    lote = insumo.lotes.order_by('fechaVencimiento', 'id').first()
    return {
        'id': insumo.id,
        'nombre': insumo.nombre,
        'tipo': insumo.tipo,
        'unidad_de_medida': insumo.unidadDeMedida,
        'fecha_vencimiento': lote.fechaVencimiento.isoformat() if lote and lote.fechaVencimiento else '',
        'stock_actual': str(lote.stockActual) if lote and lote.stockActual is not None else '0',
    }


def insumos(request):
    insumos_qs = Insumo.objects.prefetch_related('lotes').all()
    total_insumos = insumos_qs.count()
    vacunas = insumos_qs.filter(tipo='Vacuna').count()
    medicamentos = insumos_qs.filter(tipo='Medicamento').count()
    alimentos = insumos_qs.filter(tipo='Alimento').count()
    stock_total = sum((lote.stockActual or Decimal('0')) for insumo in insumos_qs for lote in insumo.lotes.all())

    return render(request, 'insumos.html', {
        'insumos': list(insumos_qs.values('id', 'nombre', 'tipo', 'unidadDeMedida')),
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
            insumo = Insumo.objects.create(
                nombre=request.POST.get('nombre', '').strip(),
                tipo=request.POST.get('tipo', 'Otros').strip() or 'Otros',
                unidadDeMedida=request.POST.get('unidadDeMedida', request.POST.get('unidad_de_medida', 'kg')).strip() or 'kg',
            )
            lote = Lote.objects.create(
                insumo=insumo,
                fechaVencimiento=_parse_fecha(request.POST.get('fecha_vencimiento') or request.POST.get('fechaVencimiento')),
                stockActual=Decimal(request.POST.get('stock_actual', request.POST.get('stockActual', '0')) or '0'),
            )
            insumo._lote_creado = lote
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        return JsonResponse({'insumo': _serialize_insumo(insumo)}, status=201)


@require_http_methods(['GET', 'POST', 'DELETE'])
def insumo_detalle(request, insumo_id):
    insumo = get_object_or_404(Insumo, pk=insumo_id)

    if request.method == 'GET':
        return JsonResponse({'insumo': _serialize_insumo(insumo)})

    if request.method == 'POST':
        try:
            insumo.nombre = request.POST.get('nombre', insumo.nombre).strip()
            insumo.tipo = request.POST.get('tipo', insumo.tipo).strip() or insumo.tipo
            insumo.unidadDeMedida = request.POST.get('unidadDeMedida', request.POST.get('unidad_de_medida', insumo.unidadDeMedida)).strip() or insumo.unidadDeMedida
            insumo.save()

            lote = insumo.lotes.order_by('fechaVencimiento', 'id').first()
            if lote is None:
                lote = Lote.objects.create(insumo=insumo)
            lote.fechaVencimiento = _parse_fecha(request.POST.get('fecha_vencimiento') or request.POST.get('fechaVencimiento'))
            lote.stockActual = Decimal(request.POST.get('stock_actual', request.POST.get('stockActual', lote.stockActual or '0')) or lote.stockActual or '0')
            lote.save()
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        return JsonResponse({'insumo': _serialize_insumo(insumo)})

    if request.method == 'DELETE':
        insumo.delete()
        return JsonResponse({'ok': True})
