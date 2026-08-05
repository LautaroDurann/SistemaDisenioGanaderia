from django.db import models

# 1. Enfermedad
class Enfermedad(models.Model):
    nombre = models.CharField(max_length=100)
    es_zoonotica = models.BooleanField(default=False)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

# 2. Diagnostico (Tabla intermedia para normalizar la relación)
class Diagnostico(models.Model):
    ESTADO_CHOICES = [
        ('Curado', 'Curado'),
        ('En tratamiento', 'En tratamiento'),
        ('Crónico', 'Crónico'),
    ]

    animal = models.ForeignKey('animales.Animal', on_delete=models.CASCADE)
    enfermedad = models.ForeignKey(Enfermedad, on_delete=models.CASCADE)
    fecha_deteccion = models.DateField()
    
    # --- CAMBIO AQUÍ ---
    # Dejó de ser BooleanField y ahora es CharField usando el ENUM. 
    # Le puse 'En tratamiento' por defecto porque tiene sentido al detectar una enfermedad.
    estado_actual = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='En tratamiento')
    
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Diagnóstico: {self.enfermedad.nombre} - Animal ID: {self.animal_id}"

# 3. Evento Sanitario (Reemplazo de la antigua tabla Tratamientos)
from django.core.exceptions import ValidationError


class EventoSanitario(models.Model):
    TIPO_CHOICES = [
        ('Vacunación', 'Vacunación'),
        ('Desparasitación', 'Desparasitación'),
        ('Antibiótico', 'Antibiótico'),
        ('Suplemento', 'Suplemento'),
        ('Castración', 'Castración'),
        ('Inseminación', 'Inseminación'),
    ]

    detalle = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    fecha_aplicacion = models.DateField()
    estado = models.BooleanField(default=True)
    costo_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lote = models.ForeignKey('inventario.Lote', on_delete=models.SET_NULL, null=True, blank=True)

    # Claves Foráneas
    animal = models.ForeignKey('animales.Animal', on_delete=models.CASCADE)
    diagnostico = models.ForeignKey(Diagnostico, on_delete=models.SET_NULL, null=True, blank=True)
    veterinario = models.ForeignKey('usuarios.Veterinario', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.tipo} ({self.fecha_aplicacion})"

    def clean(self):
        if self.tipo == 'Inseminación' and self.animal and self.animal.sexo != 'Hembra':
            raise ValidationError('Solo se puede registrar inseminación para hembras.')
        if self.tipo == 'Vacunación' and self.estado and self.lote and (self.cantidad is None or self.cantidad <= 0):
            raise ValidationError('Si la vacunación se aplicó, debe indicar un lote y la cantidad consumida.')
        if self.tipo == 'Castración' and self.animal and self.animal.castrado:
            raise ValidationError('El animal ya está castrado.')

    def save(self, *args, **kwargs):
        from django.db import transaction
        from inventario.models import Consumo

        self.full_clean()
        old_evento = None
        if self.pk:
            try:
                old_evento = EventoSanitario.objects.select_related('lote').get(pk=self.pk)
            except EventoSanitario.DoesNotExist:
                old_evento = None

        with transaction.atomic():
            super().save(*args, **kwargs)

            if self.tipo == 'Castración' and not self.animal.castrado:
                self.animal.castrado = True
                self.animal.save(update_fields=['castrado'])

            if self.tipo == 'Vacunación' and self.estado and self.lote and self.cantidad:
                consumo, created = Consumo.objects.get_or_create(
                    evento_sanitario=self,
                    defaults={'lote': self.lote, 'cantidad': self.cantidad},
                )
                if created:
                    if self.lote.stockActual is not None:
                        self.lote.stockActual = max(self.lote.stockActual - self.cantidad, 0)
                        self.lote.save(update_fields=['stockActual'])
                else:
                    if consumo.lote_id != self.lote_id:
                        if consumo.lote.stockActual is not None:
                            consumo.lote.stockActual = max(consumo.lote.stockActual + (consumo.cantidad or 0), 0)
                            consumo.lote.save(update_fields=['stockActual'])
                        consumo.lote = self.lote
                        consumo.cantidad = self.cantidad
                        consumo.save()
                        if self.lote.stockActual is not None:
                            self.lote.stockActual = max(self.lote.stockActual - self.cantidad, 0)
                            self.lote.save(update_fields=['stockActual'])
                    elif self.cantidad != consumo.cantidad:
                        delta = self.cantidad - (consumo.cantidad or 0)
                        if self.lote.stockActual is not None:
                            self.lote.stockActual = max(self.lote.stockActual - delta, 0)
                            self.lote.save(update_fields=['stockActual'])
                        consumo.cantidad = self.cantidad
                        consumo.save()
            else:
                consumo = Consumo.objects.filter(evento_sanitario=self).first()
                if consumo:
                    if consumo.lote.stockActual is not None:
                        consumo.lote.stockActual = max(consumo.lote.stockActual + (consumo.cantidad or 0), 0)
                        consumo.lote.save(update_fields=['stockActual'])
                    consumo.delete()
