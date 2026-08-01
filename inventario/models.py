from django.db import models

# 1. Insumo
class Insumo(models.Model):
    nombre = models.CharField(max_length=100)
    unidad_de_medida = models.CharField(max_length=20, default='kg')
    fecha_vencimiento = models.DateField(null=True, blank=True)
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.nombre} (Stock: {self.stock_actual})"

# 2. Detalle de Compra (Conecta Compra con Insumo)
class DetalleCompra(models.Model):
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    
    compra = models.ForeignKey('finanzas.Compra', on_delete=models.CASCADE, related_name='detalles')
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.cantidad} x {self.insumo.nombre} (Compra {self.compra.id})"

# 3. Consumo (Conecta Insumo con Evento Sanitario)
class Consumo(models.Model):
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    evento_sanitario = models.ForeignKey('sanidad.EventoSanitario', on_delete=models.CASCADE)

    def __str__(self):
        return f"Consumo: {self.cantidad} de {self.insumo.nombre}"

# 4. Dieta
class Dieta(models.Model):
    nombre = models.CharField(max_length=100)
    porcentaje_proteina = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

# 5. Composición de Dieta (Conecta Dieta con Insumo)
class ComposicionDieta(models.Model):
    cantidad_por_porcion = models.DecimalField(max_digits=10, decimal_places=2)
    
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    dieta = models.ForeignKey(Dieta, on_delete=models.CASCADE, related_name='composicion')

    def __str__(self):
        return f"{self.cantidad_por_porcion} de {self.insumo.nombre} en {self.dieta.nombre}"

# 6. Registro de Alimentación
class RegistroAlimentacion(models.Model):
    # En tu documento decía INT para fecha, pero lo correcto y más útil es DateField
    fecha = models.DateField() 
    
    parcela = models.ForeignKey('establecimientos.Parcela', on_delete=models.CASCADE)
    dieta = models.ForeignKey(Dieta, on_delete=models.CASCADE)

    def __str__(self):
        return f"Alimentación en {self.parcela} - {self.fecha}"
    #dd