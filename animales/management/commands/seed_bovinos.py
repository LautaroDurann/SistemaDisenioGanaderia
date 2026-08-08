from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from animales.models import Animal, MovimientoAnimal, Preniez
from establecimientos.models import Establecimiento, Parcela


def _peso(value):
    return Decimal(str(value))


POTREROS = [
    ('Potrero Norte', 500, 400, Parcela.ESTADO_EN_PASTOREO),
    ('Potrero Sud', 600, 350, Parcela.ESTADO_EN_PASTOREO),
    ('Potrero Este', 450, 420, Parcela.ESTADO_EN_DESCANSO),
    ('Potrero Oeste', 550, 380, Parcela.ESTADO_EN_PASTOREO),
    ('Corral', 120, 90, Parcela.ESTADO_EN_MANTENIMIENTO),
]

KG_PRECIO = {'Toro': '3200', 'Vaca': '2800', 'Ternero': '3500'}

# (caravana, nombre, raza, color, nacimiento, peso_actual, potrero)
TOROS = [
    (2500100101, 'Rey', 'Angus', 'Negro', date(2019, 3, 12), 920, 'Potrero Norte'),
    (2500100102, 'Don Juan', 'Braford', 'Colorado', date(2020, 5, 2), 880, 'Potrero Norte'),
    (2500100103, 'Pampa', 'Hereford', 'Colorado', date(2019, 11, 20), 850, 'Potrero Norte'),
    (2500100104, 'Galeno', 'Brangus', 'Barcino', date(2021, 2, 14), 800, 'Potrero Norte'),
]

# (caravana, nombre, raza, color, nacimiento, peso_actual, potrero)
VACAS = [
    (2500100201, 'Paloma', 'Braford', 'Colorado', date(2020, 9, 15), 520, 'Potrero Norte'),
    (2500100202, 'Luna', 'Angus', 'Negro', date(2021, 4, 3), 510, 'Potrero Sud'),
    (2500100203, 'Mora', 'Braford', 'Overo', date(2019, 8, 22), 540, 'Potrero Norte'),
    (2500100204, 'Nina', 'Hereford', 'Colorado', date(2022, 1, 18), 490, 'Potrero Sud'),
    (2500100205, 'Aurora', 'Angus', 'Negro', date(2020, 11, 30), 530, 'Potrero Sud'),
    (2500100206, 'Canela', 'Braford', 'Colorado', date(2021, 7, 11), 505, 'Potrero Este'),
    (2500100207, 'Dulce', 'Brangus', 'Barcino', date(2019, 5, 25), 560, 'Potrero Oeste'),
    (2500100208, 'Estrella', 'Hereford', 'Colorado', date(2022, 3, 7), 480, 'Potrero Este'),
    (2500100209, 'Flora', 'Angus', 'Negro', date(2021, 10, 19), 515, 'Potrero Este'),
    (2500100210, 'Gringa', 'Braford', 'Colorado', date(2020, 2, 10), 545, 'Potrero Sud'),
    (2500100211, 'Jacinta', 'Brangus', 'Barcino', date(2022, 6, 28), 470, 'Potrero Este'),
    (2500100212, 'Lucía', 'Hereford', 'Colorado', date(2019, 12, 5), 555, 'Potrero Sud'),
    (2500100213, 'Mancha', 'Braford', 'Overo', date(2021, 1, 29), 525, 'Potrero Oeste'),
    (2500100214, 'Morena', 'Angus', 'Negro', date(2023, 4, 21), 460, 'Potrero Oeste'),
    (2500100215, 'Negra', 'Angus', 'Negro', date(2022, 8, 14), 485, 'Potrero Norte'),
    (2500100216, 'Ñata', 'Braford', 'Colorado', date(2020, 6, 17), 535, 'Potrero Oeste'),
    (2500100217, 'Perla', 'Hereford', 'Colorado', date(2021, 12, 9), 495, 'Potrero Este'),
    (2500100218, 'Rosa', 'Brangus', 'Colorado', date(2023, 2, 26), 450, 'Potrero Este'),
    (2500100219, 'Sombra', 'Angus', 'Negro', date(2022, 10, 5), 475, 'Potrero Oeste'),
    (2500100220, 'Violeta', 'Braford', 'Colorado', date(2020, 3, 31), 550, 'Potrero Oeste'),
]

# (caravana, nombre, sexo, raza, color, nacimiento, peso_actual, madre_caravana)
TERNEROS = [
    (2500100301, 'Pitufo', 'Macho', 'Braford', 'Colorado', date(2026, 2, 18), 185, 2500100201),
    (2500100302, 'Pelusa', 'Hembra', 'Angus', 'Negro', date(2026, 2, 10), 170, 2500100202),
    (2500100303, 'Roco', 'Macho', 'Braford', 'Overo', date(2026, 3, 5), 175, 2500100203),
    (2500100304, 'Manchita', 'Hembra', 'Hereford', 'Colorado', date(2026, 2, 27), 165, 2500100204),
    (2500100305, 'Bombón', 'Macho', 'Angus', 'Negro', date(2026, 3, 27), 165, 2500100205),
    (2500100306, 'Rosita', 'Hembra', 'Braford', 'Colorado', date(2026, 3, 16), 155, 2500100206),
    (2500100307, 'Tornillo', 'Macho', 'Brangus', 'Barcino', date(2026, 4, 15), 150, 2500100207),
    (2500100308, 'Nube', 'Hembra', 'Hereford', 'Colorado', date(2026, 4, 3), 145, 2500100208),
    (2500100309, 'Chispa', 'Macho', 'Braford', 'Colorado', date(2026, 5, 2), 135, 2500100209),
    (2500100310, 'Chinita', 'Hembra', 'Angus', 'Negro', date(2026, 4, 28), 130, 2500100210),
    (2500100311, 'Tero', 'Macho', 'Brangus', 'Barcino', date(2026, 5, 22), 120, 2500100211),
    (2500100312, 'Ambar', 'Hembra', 'Braford', 'Colorado', date(2026, 5, 17), 115, 2500100212),
    (2500100313, 'Firpo', 'Macho', 'Hereford', 'Colorado', date(2026, 6, 11), 105, 2500100213),
    (2500100314, 'Linda', 'Hembra', 'Angus', 'Negro', date(2026, 6, 6), 100, 2500100214),
    (2500100315, 'Coco', 'Macho', 'Braford', 'Overo', date(2026, 7, 1), 85, 2500100215),
    (2500100316, 'Bety', 'Hembra', 'Angus', 'Negro', date(2026, 6, 25), 85, 2500100216),
]

# (caravana_madre, tipo, fecha_servicio, estado, costo)
PRENIEZ = [
    (2500100201, 'Natural', date(2026, 4, 20), 'Preñada', None),
    (2500100203, 'Natural', date(2026, 3, 25), 'Preñada', None),
    (2500100204, 'Inseminación', date(2026, 5, 5), 'Preñada', _peso('25000.00')),
    (2500100205, 'Inseminación', date(2026, 4, 10), 'Preñada', _peso('25000.00')),
    (2500100207, 'Natural', date(2026, 3, 30), 'Preñada', None),
    (2500100209, 'Inseminación', date(2026, 5, 12), 'Preñada', _peso('25000.00')),
    (2500100211, 'Natural', date(2026, 4, 2), 'Preñada', None),
    (2500100217, 'Natural', date(2026, 4, 25), 'Preñada', None),
    (2500100202, 'Natural', date(2026, 6, 1), 'A confirmar', None),
    (2500100206, 'Natural', date(2026, 6, 10), 'A confirmar', None),
]


class Command(BaseCommand):
    help = 'Carga 40 bovinos de prueba (4 toros, 20 vacas y 16 terneros) con datos creibles.'

    def add_arguments(self, parser):
        parser.add_argument('--establecimiento-id', type=int, default=None, help='Establecimiento destino (por defecto el primero).')

    def _establecimiento(self, establecimiento_id):
        if establecimiento_id is not None:
            return Establecimiento.objects.get(pk=establecimiento_id)
        return Establecimiento.objects.first()

    def _potrero(self, establecimiento, nombre):
        potrero, _ = Parcela.objects.get_or_create(
            establecimiento=establecimiento,
            descripcion=nombre,
            defaults={'ancho': 100, 'largo': 100, 'estado': Parcela.ESTADO_EN_PASTOREO},
        )
        return potrero

    def _crear_animal(self, caravana, nombre, sexo, raza, color, nacimiento, peso_actual, categoria, potrero, madre=None, padre=None, costo=None):
        peso = _peso(peso_actual)
        peso_al_nacer = _peso('30.00') if categoria == 'Ternero' else _peso('36.00')
        peso_al_destete = None if categoria == 'Ternero' else _peso('200.00')
        animal, creado = Animal.objects.get_or_create(
            id_senasa=caravana,
            defaults={
                'nombre': nombre,
                'tipo_animal': 'Bovino',
                'sexo': sexo,
                'raza': raza,
                'color': color,
                'fecha_nacimiento': nacimiento,
                'peso_al_nacer': peso_al_nacer,
                'peso_al_destete': peso_al_destete,
                'peso_actual': peso,
                'costo_adquisicion': costo,
                'precio_venta': _peso(round(float(peso_actual) * float(KG_PRECIO[categoria]), 2)),
                'castrado': False,
                'madre': madre,
                'padre': padre,
                'parcela': potrero,
                'establecimiento': potrero.establecimiento,
            },
        )
        return animal, creado

    @transaction.atomic
    def handle(self, *args, **options):
        establecimiento = self._establecimiento(options['establecimiento_id'])
        if establecimiento is None:
            self.stderr.write(self.style.ERROR('No hay ningún establecimiento registrado.'))
            return

        potreros = {}
        for nombre, ancho, largo, estado in POTREROS:
            potrero, _ = Parcela.objects.get_or_create(
                establecimiento=establecimiento,
                descripcion=nombre,
                defaults={'ancho': ancho, 'largo': largo, 'estado': estado},
            )
            potreros[nombre] = potrero

        creados = 0
        toros = {}

        for caravana, nombre, raza, color, nacimiento, peso, potrero in TOROS:
            animal, creado = self._crear_animal(
                caravana, nombre, 'Macho', raza, color, nacimiento, peso,
                'Toro', potreros[potrero], costo=_peso('2400000.00'),
            )
            toros[caravana] = animal
            if creado:
                creados += 1
                MovimientoAnimal.objects.create(
                    animal=animal, fecha=nacimiento, tipo='Alta',
                    destino=potreros[potrero], observaciones='Ingreso como reproductor.',
                )

        vacas = {}
        for caravana, nombre, raza, color, nacimiento, peso, potrero in VACAS:
            animal, creado = self._crear_animal(
                caravana, nombre, 'Hembra', raza, color, nacimiento, peso,
                'Vaca', potreros[potrero], costo=_peso('1100000.00'),
            )
            vacas[caravana] = animal
            if creado:
                creados += 1
                MovimientoAnimal.objects.create(
                    animal=animal, fecha=nacimiento, tipo='Alta',
                    destino=potreros[potrero], observaciones='Ingreso como madre.',
                )

        padres = list(toros.values())
        for i, (caravana, nombre, sexo, raza, color, nacimiento, peso, madre_caravana) in enumerate(TERNEROS):
            madre = vacas[madre_caravana]
            padre = padres[i % len(padres)]
            potrero = madre.parcela
            animal, creado = self._crear_animal(
                caravana, nombre, sexo, raza, color, nacimiento, peso,
                'Ternero', potrero, madre=madre, padre=padre, costo=None,
            )
            if creado:
                creados += 1
                MovimientoAnimal.objects.create(
                    animal=animal, fecha=nacimiento, tipo='Nacimiento',
                    destino=potrero, observaciones='Nacimiento en el establecimiento.',
                )

        prenieces = 0
        for caravana_madre, tipo, fecha, estado, costo in PRENIEZ:
            madre = vacas.get(caravana_madre)
            if madre is None:
                continue
            _, fue_creada = Preniez.objects.get_or_create(
                madre=madre, fecha=fecha, tipo=tipo,
                defaults={'estado_actual': estado, 'costo_inseminacion': costo},
            )
            if fue_creada:
                prenieces += 1

        total = Animal.objects.filter(establecimiento=establecimiento, tipo_animal='Bovino').count()
        self.stdout.write(self.style.SUCCESS(
            f'Bovinos cargados: {creados} nuevos (total en {establecimiento.nombre}: {total}). '
            f'Preñeces registradas: {prenieces}.'
        ))
        self.stdout.write('Toros: 4 | Vacas: 20 | Terneros: 16')
