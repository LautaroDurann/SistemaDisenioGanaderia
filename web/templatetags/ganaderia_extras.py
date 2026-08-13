import calendar
from datetime import date

from django import template

register = template.Library()


@register.filter
def categoria(animal):
    """Clasificación exclusiva de bovinos para el stock (idéntica a la vista)."""
    if animal.tipo_animal != 'Bovino':
        return ''
    peso = animal.peso_actual
    if _es_ternero(animal) and peso is not None and peso <= 400:
        return 'Ternero'
    return 'Toro' if animal.sexo == 'Macho' else 'Vaca'


def _es_ternero(animal):
    if not animal.fecha_nacimiento:
        return False
    mes_limite = animal.fecha_nacimiento.month + 6
    anio_limite = animal.fecha_nacimiento.year + (mes_limite - 1) // 12
    mes_limite = (mes_limite - 1) % 12 + 1
    dia_limite = min(animal.fecha_nacimiento.day, calendar.monthrange(anio_limite, mes_limite)[1])
    return date.today() <= date(anio_limite, mes_limite, dia_limite)
