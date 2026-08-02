from django.contrib import admin

from .models import Persona, Veterinario, Proveedor, Comprador, Usuario, RolEstablecimiento, Telefono

admin.site.register(Persona)
admin.site.register(Veterinario)
admin.site.register(Proveedor)
admin.site.register(Comprador)
admin.site.register(Usuario)
admin.site.register(RolEstablecimiento)
admin.site.register(Telefono)