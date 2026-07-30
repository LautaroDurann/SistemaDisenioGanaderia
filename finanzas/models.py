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
    
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    fecha = models.DateField()
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    detalle = models.TextField(blank=True, null=True)
    
    # Claves Foráneas
    proveedor = models.ForeignKey('usuarios.Proveedor', on_delete=models.SET_NULL, null=True)
    # Usamos OneToOneField porque una compra genera un único movimiento financiero
    mov_financiero = models.OneToOneField(MovimientoFinanciero, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Compra {self.tipo} - {self.fecha}"

# 3. Venta
class Venta(models.Model):
    tipo = models.CharField(max_length=100)
    fecha = models.DateField()
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    detalle = models.TextField(blank=True, null=True)
    
    # Claves Foráneas
    comprador = models.ForeignKey('usuarios.Comprador', on_delete=models.SET_NULL, null=True)
    mov_financiero = models.OneToOneField(MovimientoFinanciero, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Venta {self.id} - {self.fecha}"