from datetime import date

from django.test import TestCase
from django.urls import reverse

from animales.models import Animal, MovimientoAnimal, Pesaje
from establecimientos.models import Establecimiento, Parcela


class WebIntegrationTests(TestCase):
    def setUp(self):
        establecimiento = Establecimiento.objects.create(
            nombre='Campo de prueba', fecha_inicio=date.today(), ubicacion='Córdoba'
        )
        self.parcela = Parcela.objects.create(ancho=10, largo=20, establecimiento=establecimiento)
        self.animal = Animal.objects.create(
            id_senasa=12345, nombre='Luna', tipo_animal='Bovino', sexo='Hembra',
            parcela=self.parcela, vivo=True,
        )

    def test_paginas_principales_responden(self):
        for url_name in ('dashboard', 'stock', 'movimientos', 'potreros', 'vacunacion', 'pesajes', 'alimentacion', 'usuarios', 'configuracion'):
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_api_stock_y_registro_de_pesaje(self):
        response = self.client.get(reverse('stock_api'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['animales'][0]['caravana'], '12345')

        response = self.client.post(reverse('crear_pesaje'), {
            'animal_id': self.animal.id, 'fecha': '2026-08-01', 'peso': '350.50',
        })
        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(str(self.animal.peso_actual), '350.50')
        self.assertEqual(Pesaje.objects.count(), 1)

    def test_crear_animal_desde_stock(self):
        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': '67890', 'nombre': 'Mora', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'raza': 'Angus', 'peso_actual': '285.00', 'parcela_id': self.parcela.id,
        })
        self.assertEqual(response.status_code, 201)
        animal = Animal.objects.get(id_senasa=67890)
        self.assertEqual(animal.parcela, self.parcela)
        self.assertEqual(str(animal.peso_actual), '285.00')
        self.assertTrue(MovimientoAnimal.objects.filter(animal=animal, tipo='Alta').exists())

    def test_crear_animal_sin_nombre(self):
        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': '67891', 'nombre': '', 'sexo': 'Macho', 'tipo_animal': 'Bovino', 'vivo': 'on',
            'peso_al_nacer': '34.5', 'peso_al_destete': '180', 'diametro_escrotal': '31.2',
        })
        self.assertEqual(response.status_code, 201)
        animal = Animal.objects.get(id_senasa=67891)
        self.assertEqual(animal.nombre, '')
        self.assertTrue(animal.vivo)
        self.assertEqual(str(animal.diametro_escrotal), '31.20')

    def test_actualizar_y_eliminar_animal(self):
        response = self.client.post(reverse('actualizar_animal', args=[self.animal.id]), {
            'id_senasa': '12345', 'nombre': 'Luna actualizada', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'raza': 'Hereford', 'peso_actual': '412.00', 'parcela_id': self.parcela.id,
        })
        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.nombre, 'Luna actualizada')
        self.assertEqual(str(self.animal.peso_actual), '412.00')
        response = self.client.post(reverse('eliminar_animal', args=[self.animal.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Animal.objects.filter(pk=self.animal.id).exists())

    def test_movimiento_actualiza_ubicacion(self):
        destino = Parcela.objects.create(ancho=30, largo=20, establecimiento=self.parcela.establecimiento)
        response = self.client.post(reverse('crear_movimiento'), {
            'animal_id': self.animal.id, 'fecha': '2026-08-01', 'tipo': 'Traslado',
            'origen_id': self.parcela.id, 'destino_id': destino.id,
        })
        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.parcela, destino)
        self.assertEqual(MovimientoAnimal.objects.count(), 1)

    def test_crear_potrero(self):
        response = self.client.post(reverse('crear_potrero'), {'ancho': '15', 'largo': '40', 'descripcion': 'Potrero nuevo'})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Parcela.objects.filter(descripcion='Potrero nuevo').exists())
