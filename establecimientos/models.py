from django.db import models

# 1. Establecimiento
class Establecimiento(models.Model):
    nombre = models.CharField(max_length=100)
    fecha_inicio = models.DateField()
    ubicacion = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

# 2. Parcela
class Parcela(models.Model):
    ESTADO_EN_PASTOREO = 'En pastoreo'
    ESTADO_EN_DESCANSO = 'En descanso'
    ESTADO_EN_MANTENIMIENTO = 'En mantenimiento'

    ESTADOS_PARCELA = [
        (ESTADO_EN_PASTOREO, 'En pastoreo'),
        (ESTADO_EN_DESCANSO, 'En descanso'),
        (ESTADO_EN_MANTENIMIENTO, 'En mantenimiento'),
    ]

    # Usamos DecimalField para las medidas (ej: 150.50 metros).
    # max_digits=8 y decimal_places=2 permite números de hasta 999999.99
    ancho = models.DecimalField(max_digits=8, decimal_places=2)
    largo = models.DecimalField(max_digits=8, decimal_places=2)
    descripcion = models.TextField(blank=True, null=True)  # TextField es mejor para textos largos que CharField
    estado = models.CharField(max_length=20, choices=ESTADOS_PARCELA, default=ESTADO_EN_PASTOREO)

    # Clave Foránea (CF): Una parcela pertenece a un establecimiento
    # on_delete=models.CASCADE significa que si borras el establecimiento, se borran sus parcelas
    establecimiento = models.ForeignKey(Establecimiento, on_delete=models.CASCADE, related_name='parcelas')

    def __str__(self):
        # Como Django crea el ID automáticamente, podemos usar self.id
        return f"Parcela {self.id} - {self.establecimiento.nombre}"
