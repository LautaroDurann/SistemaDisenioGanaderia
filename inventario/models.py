from django.db import models


class Insumo(models.Model):
    TIPO_CHOICES = [
        ('Vacuna', 'Vacuna'),
        ('Medicamento', 'Medicamento'),
        ('Alimento', 'Alimento'),
        ('Otros', 'Otros'),
    ]

    nombre = models.CharField(max_length=100, null=True, blank=True)
    unidadDeMedida = models.CharField(max_length=50, null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, null=True, blank=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre or 'Insumo sin nombre'} (ID: {self.id})"


class Lote(models.Model):
    fechaVencimiento = models.DateField(null=True, blank=True)
    stockActual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name='lotes', null=True, blank=True)

    class Meta:
        ordering = ['fechaVencimiento', 'id']

    def __str__(self):
        return f"Lote {self.id} - {self.insumo}"


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


class Dieta(models.Model):
    nombre = models.CharField(max_length=100)
    porcentaje_proteina = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre


class ComposicionDieta(models.Model):
    cantidadPorPorcion = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name='composiciones_dieta')
    dieta = models.ForeignKey('inventario.Dieta', on_delete=models.CASCADE, related_name='composiciones')

    def __str__(self):
        return f"Composición {self.id} - Dieta {self.dieta.id}"


class RegistroAlimentacion(models.Model):
    fecha = models.DateField()

    parcela = models.ForeignKey('establecimientos.Parcela', on_delete=models.CASCADE)
    dieta = models.ForeignKey(Dieta, on_delete=models.CASCADE)

    def __str__(self):
        return f"Alimentación en {self.parcela} - {self.fecha}"