from decimal import Decimal

from django.db import models

# 1. Movimiento Financiero (Centraliza todos los ingresos y egresos)
class MovimientoFinanciero(models.Model):
    TIPO_CHOICES = [
        ('Ingreso', 'Ingreso'),
        ('Egreso', 'Egreso'),
    ]
    
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    nombre = models.CharField(max_length=100)
    detalle = models.TextField(blank=True, null=True)
    fecha = models.DateField()

    # Establecimiento al que pertenece el movimiento (ventas, compras y gastos propios).
    establecimiento = models.ForeignKey(
        'establecimientos.Establecimiento', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='movimientos_financieros',
    )

    def __str__(self):
        return f"{self.tipo}: {self.nombre} (${self.monto_total})"

# 2. Compra
class Compra(models.Model):
    TIPO_CHOICES = [
        ('Animales', 'Animales'),
        ('Insumos', 'Insumos'),
        ('Maquinaria', 'Maquinaria'),
        ('Otros', 'Otros'),
    ]
    ESTADO_PAGO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('Pagada', 'Pagada'),
    ]
    METODO_PAGO_CHOICES = [
        ('Efectivo', 'Efectivo'),
        ('Transferencia', 'Transferencia'),
        ('Cheque', 'Cheque'),
    ]
    
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    fecha = models.DateField()
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    detalle = models.TextField(blank=True, null=True)
    estadoDePago = models.CharField(max_length=20, choices=ESTADO_PAGO_CHOICES, default='Pendiente')
    metodoDePago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES, default='Efectivo')
    
    # Claves Foráneas
    proveedor = models.ForeignKey('usuarios.Proveedor', on_delete=models.SET_NULL, null=True, blank=True)
    # Usamos OneToOneField porque una compra genera un único movimiento financiero
    mov_financiero = models.OneToOneField(MovimientoFinanciero, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Compra {self.tipo} - {self.fecha}"

# 3. Venta
class Venta(models.Model):
    ESTADO_COBRO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('Pagada', 'Pagada'),
    ]
    METODO_PAGO_CHOICES = [
        ('Efectivo', 'Efectivo'),
        ('Transferencia', 'Transferencia'),
        ('Cheque', 'Cheque'),
    ]

    tipo = models.CharField(max_length=100)
    fecha = models.DateField()
    # El peso se conserva en la venta para que el comprobante no cambie.
    peso_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Porcentaje que se descuenta del peso total (bosta, barro, etc.) antes de facturar.
    porcentajeDesbaste = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    precio_por_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    detalle = models.TextField(blank=True, null=True)
    estadoDeCobro = models.CharField(max_length=20, choices=ESTADO_COBRO_CHOICES, default='Pendiente')
    metodoDePago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES, default='Efectivo')
    
    # Claves Foráneas
    comprador = models.ForeignKey('usuarios.Comprador', on_delete=models.SET_NULL, null=True, blank=True)
    mov_financiero = models.OneToOneField(MovimientoFinanciero, on_delete=models.CASCADE, null=True, blank=True)

    @property
    def peso_desbastado(self):
        """Peso total descontado el porcentaje de desbaste."""
        descuento = (self.porcentajeDesbaste or Decimal('0')) / Decimal('100')
        return (self.peso_total * (1 - descuento)).quantize(Decimal('0.01'))

    def __str__(self):
        return f"Venta {self.id} - {self.fecha}"
