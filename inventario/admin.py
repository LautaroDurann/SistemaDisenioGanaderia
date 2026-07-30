from django.contrib import admin
from .models import Insumo, DetalleCompra, Consumo, Dieta, ComposicionDieta, RegistroAlimentacion

admin.site.register(Insumo)
admin.site.register(DetalleCompra)
admin.site.register(Consumo)
admin.site.register(Dieta)
admin.site.register(ComposicionDieta)
admin.site.register(RegistroAlimentacion)