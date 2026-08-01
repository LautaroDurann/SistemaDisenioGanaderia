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
class EventoSanitario(models.Model):
    TIPO_CHOICES = [
        ('Vacunación', 'Vacunación'),
        ('Desparasitación', 'Desparasitación'),
        ('Antibiótico', 'Antibiótico'),
        ('Suplemento', 'Suplemento'),
    ]

    detalle = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    fecha_aplicacion = models.DateField()
    estado = models.BooleanField(default=True)
    costo_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Claves Foráneas
    animal = models.ForeignKey('animales.Animal', on_delete=models.CASCADE)
    diagnostico = models.ForeignKey(Diagnostico, on_delete=models.SET_NULL, null=True, blank=True)
    veterinario = models.ForeignKey('usuarios.Veterinario', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.tipo} ({self.fecha_aplicacion})"