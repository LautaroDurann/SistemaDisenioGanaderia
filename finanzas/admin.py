from django.contrib import admin
from .models import LiquidacionSueldo, MovimientoFinanciero, Compra, Venta

admin.site.register(MovimientoFinanciero)
admin.site.register(Compra)
admin.site.register(Venta)
admin.site.register(LiquidacionSueldo)