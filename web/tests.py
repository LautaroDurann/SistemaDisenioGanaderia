import base64
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from animales.models import Animal, MovimientoAnimal, Pesaje
from establecimientos.models import Establecimiento, Parcela
from finanzas.models import Compra, MovimientoFinanciero, Venta
from sanidad.models import DetalleEvento, EventoSanitario
from usuarios.models import Comprador


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
        for url_name in ('dashboard', 'stock', 'movimientos', 'potreros', 'vacunacion', 'sanidad', 'pesajes', 'alimentacion', 'usuarios', 'configuracion'):
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_crear_evento_sanitario(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación',
            'fecha_aplicacion': '2026-08-01',
            'estado': 'true',
            'animal_id': self.animal.id,
            'detalle': 'Desparasitación de prueba',
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(tipo='Desparasitación', fecha_aplicacion='2026-08-01')
        self.assertTrue(evento.detalles.filter(animal=self.animal).exists())

    def test_evento_aplicado_con_costo_genera_egreso_en_finanzas(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'true',
            'costo_total': '5000.50', 'animal_id': self.animal.id,
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertIsNotNone(evento.mov_financiero)
        movimiento = evento.mov_financiero
        self.assertEqual(movimiento.tipo, 'Egreso')
        self.assertEqual(movimiento.monto_total, Decimal('5000.50'))
        self.assertEqual(movimiento.fecha.isoformat(), '2026-08-01')
        self.assertEqual(movimiento.nombre, f'Evento sanitario #{evento.id}')
        self.assertIn('Sanidad', movimiento.detalle)

    def test_evento_aplicado_sin_costo_no_genera_movimiento(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'true',
            'costo_total': '0', 'animal_id': self.animal.id,
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertIsNone(evento.mov_financiero)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_evento_pendiente_con_costo_no_genera_movimiento(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'false',
            'costo_total': '5000.00', 'animal_id': self.animal.id,
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertIsNone(evento.mov_financiero)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_cambiar_evento_a_pendiente_elimina_el_movimiento_financiero(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'true',
            'costo_total': '5000.00', 'animal_id': self.animal.id,
        })
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertEqual(MovimientoFinanciero.objects.count(), 1)

        response = self.client.post(reverse('actualizar_evento_sanitario', args=[evento.id]), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'false',
            'costo_total': '5000.00', 'animal_id': self.animal.id,
        })
        self.assertEqual(response.status_code, 200)
        evento.refresh_from_db()
        self.assertIsNone(evento.mov_financiero)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_eliminar_evento_con_costo_elimina_el_movimiento_financiero(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'true',
            'costo_total': '5000.00', 'animal_id': self.animal.id,
        })
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertEqual(MovimientoFinanciero.objects.count(), 1)

        response = self.client.post(reverse('eliminar_evento_sanitario', args=[evento.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventoSanitario.objects.filter(pk=evento.id).exists())
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_crear_y_editar_movimiento_financiero(self):
        response = self.client.post(reverse('api_finanzas_movimientos'), {
            'fecha': '2026-08-01', 'tipo': 'Egreso', 'nombre': 'Compra de insumos',
            'detalle': 'Compra inicial', 'monto_total': '1500.00',
        })
        self.assertEqual(response.status_code, 201)
        movimiento_id = response.json()['movimiento']['id']

        response = self.client.post(reverse('actualizar_movimiento_financiero', args=[movimiento_id]), {
            'fecha': '2026-08-02', 'tipo': 'Ingreso', 'nombre': 'Venta editada',
            'detalle': 'Editado', 'monto_total': '2000.00',
        })
        self.assertEqual(response.status_code, 200)
        movimiento = MovimientoFinanciero.objects.get(pk=movimiento_id)
        self.assertEqual(movimiento.fecha.isoformat(), '2026-08-02')
        self.assertEqual(movimiento.tipo, 'Ingreso')
        self.assertEqual(movimiento.nombre, 'Venta editada')
        self.assertEqual(movimiento.detalle, 'Editado')
        self.assertEqual(str(movimiento.monto_total), '2000.00')

    def test_editar_costo_del_movimiento_sincroniza_la_venta(self):
        self.animal.peso_actual = Decimal('300.00')
        self.animal.save(update_fields=['peso_actual'])
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-03', 'tipo': 'Venta de hacienda', 'precio_por_kg': '2500.50',
            'detalle': 'Venta de prueba', 'animales': [self.animal.id],
        })
        self.assertEqual(response.status_code, 201)
        venta = Venta.objects.get(pk=response.json()['id'])
        movimiento_id = venta.mov_financiero.id

        response = self.client.post(reverse('actualizar_movimiento_financiero', args=[movimiento_id]), {
            'fecha': '2026-08-03', 'tipo': 'Ingreso', 'nombre': 'Venta editada', 'monto_total': '900000.00',
        })
        self.assertEqual(response.status_code, 200)
        venta.refresh_from_db()
        self.assertEqual(venta.monto_total, Decimal('900000.00'))
        self.assertEqual(venta.mov_financiero.monto_total, Decimal('900000.00'))

    def test_editar_costo_del_movimiento_sincroniza_el_evento_sanitario(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'true',
            'costo_total': '5000.00', 'animal_id': self.animal.id,
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        movimiento_id = evento.mov_financiero_id

        response = self.client.post(reverse('actualizar_movimiento_financiero', args=[movimiento_id]), {
            'fecha': '2026-08-01', 'tipo': 'Egreso', 'nombre': 'Evento sanitario', 'monto_total': '7500.00',
        })
        self.assertEqual(response.status_code, 200)
        evento.refresh_from_db()
        self.assertEqual(evento.costo_total, Decimal('7500.00'))
        self.assertEqual(evento.mov_financiero.monto_total, Decimal('7500.00'))

    def test_editar_costo_del_movimiento_sincroniza_la_compra(self):
        movimiento = MovimientoFinanciero.objects.create(
            fecha='2026-08-01', tipo='Egreso', nombre='Compra de insumos', monto_total=Decimal('10000.00')
        )
        compra = Compra.objects.create(
            tipo='Insumos', fecha='2026-08-01', monto_total=Decimal('10000.00'), mov_financiero=movimiento
        )

        response = self.client.post(reverse('actualizar_movimiento_financiero', args=[movimiento.id]), {
            'fecha': '2026-08-01', 'tipo': 'Egreso', 'nombre': 'Compra de insumos', 'monto_total': '12000.00',
        })
        self.assertEqual(response.status_code, 200)
        compra.refresh_from_db()
        self.assertEqual(compra.monto_total, Decimal('12000.00'))
        self.assertEqual(compra.mov_financiero.monto_total, Decimal('12000.00'))

    def test_validacion_de_castracion_muestra_la_caravana_del_animal(self):
        evento = EventoSanitario.objects.create(tipo='Castración', fecha_aplicacion='2026-08-01', estado=True)
        self.animal.castrado = True
        self.animal.save(update_fields=['castrado'])

        detalle = DetalleEvento(evento=evento, animal=self.animal)

        with self.assertRaises(ValidationError) as error:
            detalle.full_clean()

        mensaje = str(error.exception)
        self.assertIn(str(self.animal.id_senasa), mensaje)
        self.assertNotIn(f'El animal {self.animal.id}', mensaje)

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

    def test_crear_animal_sin_id_senasa_y_con_foto(self):
        foto = SimpleUploadedFile(
            'animal.png',
            base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQABAA0A5g4hBAAAAABJRU5ErkJggg=='),
            content_type='image/png',
        )
        response = self.client.post(reverse('crear_animal'), {
            'nombre': 'Mila', 'sexo': 'Hembra', 'tipo_animal': 'Bovino', 'vivo': 'on',
            'peso_actual': '280.00', 'parcela_id': self.parcela.id,
            'foto': foto,
        })
        self.assertEqual(response.status_code, 201)
        animal = Animal.objects.get(nombre='Mila')
        self.assertIsNone(animal.id_senasa)
        self.assertTrue(animal.foto.name)

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
        response = self.client.post(reverse('crear_potrero'), {
            'ancho': '15', 'largo': '40', 'descripcion': 'Potrero nuevo', 'estado': 'En pastoreo',
        })
        self.assertEqual(response.status_code, 201)
        parcela = Parcela.objects.get(descripcion='Potrero nuevo')
        self.assertEqual(parcela.estado, 'En pastoreo')

    def test_crear_potrero_sin_establecimiento_crea_uno_por_defecto(self):
        Establecimiento.objects.all().delete()
        response = self.client.post(reverse('crear_potrero'), {
            'ancho': '10', 'largo': '20', 'descripcion': 'Parcela nueva', 'estado': 'En descanso',
        })
        self.assertEqual(response.status_code, 201)
        parcela = Parcela.objects.get(descripcion='Parcela nueva')
        self.assertEqual(parcela.estado, 'En descanso')
        self.assertTrue(Establecimiento.objects.filter(nombre='Establecimiento principal').exists())

    def test_actualizar_potrero(self):
        response = self.client.post(reverse('crear_potrero'), {
            'id': self.parcela.id, 'ancho': '25', 'largo': '50', 'descripcion': 'Parcela editada', 'estado': 'En descanso',
        })
        self.assertEqual(response.status_code, 200)
        self.parcela.refresh_from_db()
        self.assertEqual(self.parcela.estado, 'En descanso')
        self.assertEqual(self.parcela.ancho, Decimal('25'))
        self.assertEqual(self.parcela.largo, Decimal('50'))

    def test_eliminar_potrero(self):
        response = self.client.post(reverse('eliminar_potrero', args=[self.parcela.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Parcela.objects.filter(pk=self.parcela.id).exists())

    def test_registrar_venta_crea_ingreso_y_actualiza_animales(self):
        self.animal.peso_actual = Decimal('300.00')
        self.animal.save(update_fields=['peso_actual'])
        segundo = Animal.objects.create(
            id_senasa=54321, nombre='Toro', tipo_animal='Bovino', sexo='Macho',
            peso_actual=Decimal('500.00'), parcela=self.parcela, vivo=True,
        )
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-03', 'tipo': 'Venta de hacienda', 'precio_por_kg': '2500.50',
            'detalle': 'Venta de prueba', 'animales': [self.animal.id, segundo.id],
        })
        self.assertEqual(response.status_code, 201)
        venta = Venta.objects.get(pk=response.json()['id'])
        self.assertEqual(venta.peso_total, Decimal('800.00'))
        self.assertEqual(venta.monto_total, Decimal('2000400.00'))
        self.assertEqual(venta.mov_financiero.tipo, 'Ingreso')
        self.assertEqual(venta.mov_financiero.fecha.isoformat(), '2026-08-03')
        self.assertEqual(MovimientoFinanciero.objects.count(), 1)
        self.animal.refresh_from_db()
        segundo.refresh_from_db()
        self.assertTrue(self.animal.vendido)
        self.assertEqual(self.animal.venta, venta)
        self.assertEqual(self.animal.precio_venta, Decimal('750150.00'))
        self.assertEqual(segundo.precio_venta, Decimal('1250250.00'))
        self.assertTrue(segundo.vendido)

        response = self.client.post(reverse('eliminar_venta', args=[venta.id]))
        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertFalse(self.animal.vendido)
        self.assertIsNone(self.animal.venta)
        self.assertFalse(Venta.objects.exists())
        self.assertFalse(MovimientoFinanciero.objects.exists())

    def test_crear_comprador_y_venta_con_peso_total_manual(self):
        self.animal.peso_actual = None
        self.animal.save(update_fields=['peso_actual'])
        response = self.client.post(reverse('crear_comprador'), {
            'dni': '22333444', 'nombre': 'Carlos', 'apellido': 'Pérez',
            'correo_electronico': 'carlos@example.com', 'fecha_nacimiento': '1990-01-15',
            'telefono': '3515551234',
        })
        self.assertEqual(response.status_code, 201)
        comprador = Comprador.objects.get(dni='22333444')
        self.assertEqual(comprador.nombre, 'Carlos')
        self.assertEqual(comprador.telefono, '3515551234')

        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-04', 'tipo': 'Venta de prueba', 'precio_por_kg': '1500.00',
            'peso_total': '420.00', 'peso_manual': 'on', 'comprador_id': comprador.id,
            'detalle': 'Venta con peso manual', 'animales': [self.animal.id],
        })
        self.assertEqual(response.status_code, 201)
        venta = Venta.objects.get(pk=response.json()['id'])
        self.assertEqual(venta.peso_total, Decimal('420.00'))
        self.assertEqual(venta.monto_total, Decimal('630000.00'))
        self.assertEqual(venta.comprador, comprador)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.precio_venta, Decimal('630000.00'))

    def test_editar_y_eliminar_comprador(self):
        comprador = Comprador.objects.create(
            dni='11222333', nombre='Ana', apellido='Gómez',
            correo_electronico='ana@example.com', fecha_nacimiento='1995-05-20', telefono='3511112222'
        )

        response = self.client.post(reverse('actualizar_comprador', args=[comprador.id]), {
            'dni': '11222333', 'nombre': 'Ana María', 'apellido': 'Gómez',
            'correo_electronico': 'ana@example.com', 'fecha_nacimiento': '1995-05-20', 'telefono': '3513334444',
        })
        self.assertEqual(response.status_code, 200)
        comprador.refresh_from_db()
        self.assertEqual(comprador.nombre, 'Ana María')
        self.assertEqual(comprador.telefono, '3513334444')

        response = self.client.post(reverse('eliminar_comprador', args=[comprador.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Comprador.objects.filter(pk=comprador.id).exists())
