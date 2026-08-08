from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase

from animales.models import Animal
from establecimientos.models import Establecimiento
from sanidad.models import DetalleEvento, EventoSanitario
from usuarios.models import Persona, RolEstablecimiento, Usuario
from web.views import _animal_data, _categoria


class AnimalStockTests(TestCase):
    def setUp(self):
        establecimiento = Establecimiento.objects.create(
            nombre='Campo animales', fecha_inicio=date.today(), ubicacion='Córdoba'
        )
        persona = Persona.objects.create(
            nombre='Juan', apellido='Fernandez', correo_electronico='juan-animales@test.com',
        )
        usuario = Usuario.objects.create(
            nombre_usuario='propietario', clave=make_password('clave123'), persona=persona,
        )
        RolEstablecimiento.objects.create(
            usuario=usuario, establecimiento=establecimiento,
            nombre='Propietario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        session = self.client.session
        session['usuario_id'] = usuario.id
        session.save()

    def crear_bovino(self, **campos):
        valores = {
            'tipo_animal': 'Bovino',
            'sexo': 'Macho',
            'fecha_nacimiento': date.today() - timedelta(days=100),
            'peso_actual': Decimal('250'),
        }
        valores.update(campos)
        return Animal.objects.create(**valores)

    def test_ternero_requiere_hasta_seis_meses_y_400_kg(self):
        self.assertEqual(_categoria(self.crear_bovino()), 'Ternero')
        self.assertEqual(_categoria(self.crear_bovino(peso_actual=Decimal('401'))), 'Toro')
        self.assertEqual(
            _categoria(self.crear_bovino(fecha_nacimiento=date.today() - timedelta(days=220))),
            'Toro',
        )

    def test_castracion_actualiza_el_estado_del_animal(self):
        animal = self.crear_bovino()
        evento = EventoSanitario.objects.create(
            tipo='Castración',
            fecha_aplicacion=date.today(),
        )
        DetalleEvento.objects.create(evento=evento, animal=animal)
        animal.refresh_from_db()
        self.assertTrue(animal.castrado)
        self.assertTrue(_animal_data(animal)['castrado'])

    def test_alta_de_animal_guarda_el_checkbox_de_castrado(self):
        respuesta = self.client.post('/api/animales/', {
            'tipo_animal': 'Bovino',
            'sexo': 'Macho',
            'castrado': 'on',
        })
        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(Animal.objects.get(pk=respuesta.json()['id']).castrado)
