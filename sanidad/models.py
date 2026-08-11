from django.db import models
from django.core.exceptions import ValidationError
from django.db import transaction

# 1. Enfermedad
class Enfermedad(models.Model):
    nombre = models.CharField(max_length=100)
    es_zoonotica = models.BooleanField(default=False)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

# 2. Diagnostico
class Diagnostico(models.Model):
    ESTADO_CHOICES = [
        ('Curado', 'Curado'),
        ('En tratamiento', 'En tratamiento'),
        ('Crónico', 'Crónico'),
    ]

    animal = models.ForeignKey('animales.Animal', on_delete=models.CASCADE)
    enfermedad = models.ForeignKey(Enfermedad, on_delete=models.CASCADE)
    fecha_deteccion = models.DateField()
    estado_actual = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='En tratamiento')
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Diagnóstico: {self.enfermedad.nombre} - Animal ID: {self.animal_id}"

def _identificador_animal(animal):
    if animal is None:
        return 'Sin animal'
    if getattr(animal, 'id_senasa', None) is not None:
        return f'#{animal.id_senasa}'
    if getattr(animal, 'nombre', None):
        return animal.nombre
    return f'ID {animal.idAnimal}'


# 3. Evento Sanitario (Cabecera - Aplica para muchos animales)
class EventoSanitario(models.Model):
    TIPO_CHOICES = [
        ('Vacunación', 'Vacunación'),
        ('Desparasitación', 'Desparasitación'),
        ('Antibiótico', 'Antibiótico'),
        ('Suplemento', 'Suplemento'),
        ('Castración', 'Castración'),
        ('Inseminación', 'Inseminación'),
        ('Otro', 'Otro'),
    ]

    detalle = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    fecha_aplicacion = models.DateField()
    estado = models.BooleanField(default=True)
    costo_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Esta cantidad ahora representa la sumatoria total del medicamento utilizado en el evento
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lote = models.ForeignKey('inventario.Lote', on_delete=models.SET_NULL, null=True, blank=True)

    # Claves Foráneas Generales
    diagnostico = models.ForeignKey(Diagnostico, on_delete=models.SET_NULL, null=True, blank=True)
    veterinario = models.ForeignKey('usuarios.Veterinario', on_delete=models.SET_NULL, null=True, blank=True)

    # Movimiento financiero que registra el gasto cuando el evento se marca como Aplicado
    mov_financiero = models.OneToOneField('finanzas.MovimientoFinanciero', on_delete=models.SET_NULL, null=True, blank=True)

    # Solo se usa para el tipo 'Inseminación': el macho que sirve de padre en el evento.
    padre = models.ForeignKey('animales.Animal', on_delete=models.SET_NULL, null=True, blank=True, related_name='eventos_inseminacion')

    # Solo se usa para el tipo 'Inseminación': características del padre donante de semen.
    padre_donante = models.CharField(max_length=255, blank=True, null=True)

    # ATENCIÓN: El campo 'animal' fue removido de aquí.

    def __str__(self):
        return f"{self.tipo} ({self.fecha_aplicacion}) - ID: {self.pk}"

    def clean(self):
        # Las validaciones del animal se fueron al DetalleEvento.
        # Aquí solo validamos cosas globales del evento (ej: Inventario)
        if self.tipo == 'Vacunación' and self.estado and self.lote and (self.cantidad is None or self.cantidad <= 0):
            raise ValidationError('Si la vacunación se aplicó, debe indicar un lote y la cantidad total consumida.')

    def save(self, *args, **kwargs):
        from inventario.models import Consumo

        self.full_clean()
        
        with transaction.atomic():
            super().save(*args, **kwargs)

            # La lógica de inventario permanece en la cabecera porque se descuenta el total
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


# 4. Detalle Evento (¡LA NUEVA TABLA INTERMEDIA!)
class DetalleEvento(models.Model):
    evento = models.ForeignKey(EventoSanitario, on_delete=models.CASCADE, related_name='detalles')
    animal = models.ForeignKey('animales.Animal', on_delete=models.CASCADE, related_name='eventos_aplicados')
    
    # Opcional: Si quieres registrar qué dosis exacta recibió cada animal, usas este campo
    cantidad_dosis = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Dosis aplicada a este animal")

    def __str__(self):
        return f"Animal: {self.animal_id} - Evento ID: {self.evento_id}"

    def clean(self):
        # Validaciones de reglas de negocio a nivel de animal individual
        if self.evento.tipo == 'Inseminación' and self.animal.sexo != 'Hembra':
            raise ValidationError(f'No se puede inseminar al animal {_identificador_animal(self.animal)} porque no es hembra.')
            
        if self.evento.tipo == 'Castración' and self.animal.castrado:
            raise ValidationError(f'El animal {_identificador_animal(self.animal)} ya figura como castrado.')

    def save(self, *args, **kwargs):
        self.full_clean()
        
        with transaction.atomic():
            super().save(*args, **kwargs)
            
            # Cambios de estado en el animal se ejecutan desde el Detalle
            if self.evento.tipo == 'Castración' and not self.animal.castrado:
                self.animal.castrado = True
                self.animal.save(update_fields=['castrado'])