from django.contrib import admin
from .models import Parto, Animal, MovimientoAnimal, Pesaje, Preniez

admin.site.register(Parto)
admin.site.register(Animal)
admin.site.register(Preniez)
admin.site.register(Pesaje)
admin.site.register(MovimientoAnimal)
