from django.db import models


class Insumo(models.Model):
    TIPO_CHOICES = [
        ('Vacuna', 'Vacuna'),
        ('Medicamento', 'Medicamento'),
        ('Otros', 'Otros'),
    ]

    nombre = models.CharField(max_length=100, null=True, blank=True)
    unidadDeMedida = models.CharField(max_length=50, null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, null=True, blank=True)

    # Baja lógica: activo=False oculta al insumo del sistema pero conserva su
    # historial (compras y consumos en eventos sanitarios).
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre or 'Insumo sin nombre'} (ID: {self.id})"


# 2. LOTE (Nueva Tabla)
class Lote(models.Model):
    # NUEVO ATRIBUTO: nombre
    nombre = models.CharField(max_length=100, null=True, blank=True)
    
    # CNN: - (Permitimos nulos)
    fechaVencimiento = models.DateField(null=True, blank=True)
    stockActual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # CF: idInsumo -> Insumo(idInsumo)
    # PROTECT: impide borrar físicamente un insumo que tiene lotes (se conserva el historial).
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='lotes', null=True, blank=True)

    # Establecimiento al que pertenece el stock del lote.
    establecimiento = models.ForeignKey(
        'establecimientos.Establecimiento', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lotes',
    )

    # Baja lógica: activo=False oculta al lote del sistema pero conserva su historial.
    activo = models.BooleanField(default=True)

    def __str__(self):
        # Ahora el panel mostrará el nombre del lote si lo tiene, o su ID si no le pusiste nombre
        nombre_mostrar = self.nombre if self.nombre else f"ID {self.id}"
        return f"Lote {nombre_mostrar} - {self.insumo}"


class DetalleCompra(models.Model):
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precioUnitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    compra = models.ForeignKey('finanzas.Compra', on_delete=models.CASCADE, related_name='detalles')
    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name='detalles_compra')

    def __str__(self):
        return f"Detalle {self.id} - Compra {self.compra.id}"


class Consumo(models.Model):
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name='consumos')
    evento_sanitario = models.ForeignKey('sanidad.EventoSanitario', on_delete=models.CASCADE)

    def __str__(self):
        return f"Consumo {self.id} (Lote: {self.lote.id})"