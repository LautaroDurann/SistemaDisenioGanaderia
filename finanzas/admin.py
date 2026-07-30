from django.contrib import admin
from .models import MovimientoFinanciero, Compra, Venta

admin.site.register(MovimientoFinanciero)
admin.site.register(Compra)
admin.site.register(Venta)