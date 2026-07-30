from django.contrib import admin
from .models import Enfermedad, Diagnostico, EventoSanitario

admin.site.register(Enfermedad)
admin.site.register(Diagnostico)
admin.site.register(EventoSanitario)