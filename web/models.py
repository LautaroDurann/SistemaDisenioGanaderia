from django.db import models


class Notificacion(models.Model):
    """Notificación del módulo Dashboard, persistida por usuario y establecimiento.

    Las alertas se calculan con datos reales del establecimiento y se sincronizan
    acá para poder marcar como leídas y eliminarlas.
    """
    usuario = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.CASCADE, related_name='notificaciones'
    )
    establecimiento = models.ForeignKey(
        'establecimientos.Establecimiento', on_delete=models.CASCADE,
        related_name='notificaciones', null=True, blank=True,
    )
    clave = models.CharField(max_length=60)
    titulo = models.CharField(max_length=200)
    detalle = models.TextField(blank=True, default='')
    icono = models.CharField(max_length=60, blank=True, default='')
    color = models.CharField(max_length=60, blank=True, default='')
    url = models.CharField(max_length=200, blank=True, default='')
    leida = models.BooleanField(default=False)
    eliminada = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activa', 'leida', '-creada']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'establecimiento', 'clave'],
                name='uniq_notificacion_por_establecimiento',
            ),
        ]

    def __str__(self):
        return self.titulo
