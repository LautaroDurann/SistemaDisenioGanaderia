import base64
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from animales.models import Animal, MovimientoAnimal, Parto, Pesaje, Preniez
from establecimientos.models import Establecimiento, Parcela
from finanzas.models import Compra, MovimientoFinanciero, Venta
from sanidad.models import DetalleEvento, EventoSanitario
from usuarios.models import Comprador
from web.views import _evento_inseminacion_data


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
        for url_name in ('dashboard', 'stock', 'movimientos', 'potreros', 'vacunacion', 'sanidad', 'pesajes', 'alimentacion', 'usuarios', 'configuracion', 'prenieces'):
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_crear_evento_sanitario(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación',
            'fecha_aplicacion': '2026-08-01',
            'estado': 'true',
            'animal_id': self.animal.idAnimal,
            'detalle': 'Desparasitación de prueba',
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(tipo='Desparasitación', fecha_aplicacion='2026-08-01')
        self.assertTrue(evento.detalles.filter(animal=self.animal).exists())

    def test_evento_aplicado_con_costo_genera_egreso_en_finanzas(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'true',
            'costo_total': '5000.50', 'animal_id': self.animal.idAnimal,
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
            'costo_total': '0', 'animal_id': self.animal.idAnimal,
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertIsNone(evento.mov_financiero)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_evento_pendiente_con_costo_no_genera_movimiento(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'false',
            'costo_total': '5000.00', 'animal_id': self.animal.idAnimal,
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertIsNone(evento.mov_financiero)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_cambiar_evento_a_pendiente_elimina_el_movimiento_financiero(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'true',
            'costo_total': '5000.00', 'animal_id': self.animal.idAnimal,
        })
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertEqual(MovimientoFinanciero.objects.count(), 1)

        response = self.client.post(reverse('actualizar_evento_sanitario', args=[evento.id]), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'false',
            'costo_total': '5000.00', 'animal_id': self.animal.idAnimal,
        })
        self.assertEqual(response.status_code, 200)
        evento.refresh_from_db()
        self.assertIsNone(evento.mov_financiero)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_eliminar_evento_con_costo_elimina_el_movimiento_financiero(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'true',
            'costo_total': '5000.00', 'animal_id': self.animal.idAnimal,
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
            'detalle': 'Venta de prueba', 'animales': [self.animal.idAnimal],
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
            'costo_total': '5000.00', 'animal_id': self.animal.idAnimal,
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
        self.assertNotIn(f'El animal {self.animal.idAnimal}', mensaje)

    def test_api_stock_y_registro_de_pesaje(self):
        response = self.client.get(reverse('stock_api'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['animales'][0]['caravana'], '12345')

        response = self.client.post(reverse('crear_pesaje'), {
            'animal_id': self.animal.idAnimal, 'fecha': '2026-08-01', 'peso': '350.50',
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
        response = self.client.post(reverse('actualizar_animal', args=[self.animal.idAnimal]), {
            'id_senasa': '12345', 'nombre': 'Luna actualizada', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'raza': 'Hereford', 'peso_actual': '412.00', 'parcela_id': self.parcela.id,
        })
        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.nombre, 'Luna actualizada')
        self.assertEqual(str(self.animal.peso_actual), '412.00')
        response = self.client.post(reverse('eliminar_animal', args=[self.animal.idAnimal]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Animal.objects.filter(pk=self.animal.idAnimal).exists())

    def test_movimiento_actualiza_ubicacion(self):
        destino = Parcela.objects.create(ancho=30, largo=20, establecimiento=self.parcela.establecimiento)
        response = self.client.post(reverse('crear_movimiento'), {
            'animal_id': self.animal.idAnimal, 'fecha': '2026-08-01', 'tipo': 'Traslado',
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
            'detalle': 'Venta de prueba', 'animales': [self.animal.idAnimal, segundo.idAnimal],
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
            'detalle': 'Venta con peso manual', 'animales': [self.animal.idAnimal],
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


class PreniezModuleTests(TestCase):
    def setUp(self):
        self.vaca = Animal.objects.create(
            id_senasa=88888, nombre='Vaca madre', tipo_animal='Bovino', sexo='Hembra', vivo=True,
        )
        self.toro = Animal.objects.create(
            id_senasa=77777, nombre='Toro padre', tipo_animal='Bovino', sexo='Macho', vivo=True,
        )
        self.datos = {
            'madre_id': self.vaca.idAnimal, 'padre_id': self.toro.idAnimal, 'fecha': '2026-08-01',
            'tipo': 'Natural', 'estado_actual': 'Preñada',
        }

    def crear_preniez(self):
        return self.client.post(reverse('crear_preniez'), self.datos)

    def test_crear_y_ver_preñez(self):
        response = self.crear_preniez()
        self.assertEqual(response.status_code, 201)
        preniez = Preniez.objects.get(pk=response.json()['preniez']['id'])
        self.assertEqual(preniez.madre, self.vaca)
        self.assertEqual(preniez.padre, self.toro)
        self.assertEqual(preniez.estado_actual, 'Preñada')
        # La fecha estimada para un bovino es fecha + 9 meses
        self.assertEqual(preniez.fecha.isoformat(), '2026-08-01')

        data = response.json()['preniez']
        self.assertEqual(data['fecha_estimada'], '2027-05-01')
        self.assertIn('Mayo', data['mes_semana_parto'])
        self.assertIn('meses', data['faltante_parto'])

    def test_no_permite_macho_como_madre(self):
        response = self.client.post(reverse('crear_preniez'), {
            'madre_id': self.toro.idAnimal, 'fecha': '2026-08-01', 'tipo': 'Natural', 'estado_actual': 'Preñada',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('hembra', response.json()['error'])

    def test_no_permite_padre_de_otro_tipo(self):
        oveja = Animal.objects.create(
            id_senasa=88889, nombre='Oveja madre', tipo_animal='Ovino', sexo='Hembra', vivo=True,
        )
        response = self.client.post(reverse('crear_preniez'), {
            'madre_id': oveja.idAnimal, 'padre_id': self.toro.idAnimal,
            'fecha': '2026-08-01', 'tipo': 'Natural', 'estado_actual': 'Preñada',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('mismo tipo', response.json()['error'])

    def test_no_permite_doble_preñez_activa(self):
        self.assertEqual(self.crear_preniez().status_code, 201)
        response = self.client.post(reverse('crear_preniez'), {
            'madre_id': self.vaca.idAnimal, 'fecha': '2026-08-02', 'tipo': 'Natural', 'estado_actual': 'Preñada',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('ya tiene una preñez activa', response.json()['error'])

    def test_inseminacion_directa_no_genera_movimiento_financiero(self):
        # El costo y el egreso de la inseminación se manejan en el EventoSanitario,
        # no en la preñez. Una preñez directa no debe crear movimientos en Finanzas.
        response = self.client.post(reverse('crear_preniez'), {
            'madre_id': self.vaca.idAnimal, 'fecha': '2026-08-01', 'tipo': 'Inseminación',
            'estado_actual': 'Preñada',
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_actualizar_preñez(self):
        preniez_id = self.crear_preniez().json()['preniez']['id']
        response = self.client.post(reverse('actualizar_preniez', args=[preniez_id]), {
            'madre_id': self.vaca.idAnimal, 'padre_id': self.toro.idAnimal, 'fecha': '2026-08-10',
            'tipo': 'Inseminación', 'estado_actual': 'A confirmar', 'detalle': 'Actualizada',
        })
        self.assertEqual(response.status_code, 200)
        preniez = Preniez.objects.get(pk=preniez_id)
        self.assertEqual(preniez.fecha.isoformat(), '2026-08-10')
        self.assertEqual(preniez.estado_actual, 'A confirmar')
        self.assertEqual(preniez.detalle, 'Actualizada')

    def test_finalizar_preñez_con_parto_y_cría(self):
        parto_id = self.crear_preniez().json()['preniez']['id']
        response = self.client.post(reverse('finalizar_preniez', args=[parto_id]), {
            'fecha': '2027-05-01', 'vivo': 'true',
        })
        self.assertEqual(response.status_code, 201)
        preniez = Preniez.objects.get(pk=parto_id)
        self.assertIsNotNone(preniez.parto)
        self.assertTrue(preniez.parto.vivo)

        # No se puede finalizar dos veces
        response = self.client.post(reverse('finalizar_preniez', args=[parto_id]), {
            'fecha': '2027-05-02', 'vivo': 'true',
        })
        self.assertEqual(response.status_code, 400)

        # Cargar la cría vinculada al parto
        response = self.client.post(reverse('crear_animal'), {
            'tipo_animal': 'Bovino', 'sexo': 'Hembra', 'nombre': 'Cría', 'madre_id': self.vaca.idAnimal,
            'fecha_nacimiento': '2027-05-01', 'parto_id': preniez.parto.id,
            'movimiento_tipo': 'Nacimiento', 'movimiento_fecha': '2027-05-01',
        })
        self.assertEqual(response.status_code, 201)
        cria = Animal.objects.get(nombre='Cría')
        self.assertEqual(cria.parto, preniez.parto)
        self.assertEqual(cria.madre, self.vaca)
        self.assertTrue(MovimientoAnimal.objects.filter(animal=cria, tipo='Nacimiento').exists())

    def test_cambiar_caravana_en_stock_no_desvincula_la_cría_del_parto(self):
        # La edición desde el módulo de Stock no envía 'parto_id'; no debe
        # desvincular a la cría de su parto (bug: se perdía el vínculo).
        preniez_id = self.crear_preniez().json()['preniez']['id']
        parto = Preniez.objects.get(pk=preniez_id)
        parto_id = self.client.post(reverse('finalizar_preniez', args=[preniez_id]), {
            'fecha': '2027-05-01', 'vivo': 'true',
        }).json()['parto']['id']
        response = self.client.post(reverse('crear_animal'), {
            'tipo_animal': 'Bovino', 'sexo': 'Hembra', 'nombre': 'Cría Stock', 'madre_id': self.vaca.idAnimal,
            'fecha_nacimiento': '2027-05-01', 'parto_id': parto_id,
            'movimiento_tipo': 'Nacimiento', 'movimiento_fecha': '2027-05-01',
        })
        self.assertEqual(response.status_code, 201)
        cria_id = response.json()['id']

        # Mismos campos que envía el formulario de Stock (sin 'parto_id').
        response = self.client.post(reverse('actualizar_animal', args=[cria_id]), {
            'tipo_animal': 'Bovino', 'sexo': 'Hembra', 'nombre': 'Cría Stock',
            'madre_id': self.vaca.idAnimal, 'id_senasa': '50000', 'vivo': 'on',
            'fecha_nacimiento': '2027-05-01',
        })
        self.assertEqual(response.status_code, 200)
        cria = Animal.objects.get(pk=cria_id)
        self.assertEqual(cria.id_senasa, 50000)
        self.assertEqual(cria.parto_id, parto_id)

    def test_eliminar_preñez_elimina_parto(self):
        response = self.client.post(reverse('crear_preniez'), {
            'madre_id': self.vaca.idAnimal, 'fecha': '2026-08-01', 'tipo': 'Inseminación',
            'estado_actual': 'Preñada',
        })
        self.assertEqual(response.status_code, 201)
        preniez_id = response.json()['preniez']['id']
        response = self.client.post(reverse('finalizar_preniez', args=[preniez_id]), {
            'fecha': '2027-05-01', 'vivo': 'false',
        })
        self.assertEqual(response.status_code, 201)

        response = self.client.post(reverse('eliminar_preniez', args=[preniez_id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Preniez.objects.filter(pk=preniez_id).exists())
        self.assertFalse(Parto.objects.exists())

    def test_pagina_preñez_incluye_especies_y_partos(self):
        response = self.client.get(reverse('prenieces'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('especies', response.context['page_data'])
        self.assertEqual(response.context['page_data']['especies'], ['Bovino', 'Porcino', 'Ovino'])
        self.assertIn('partos', response.context['page_data'])

        response = self.client.post(reverse('crear_preniez'), {
            'madre_id': self.vaca.idAnimal, 'fecha': '2026-08-01', 'tipo': 'Natural',
            'estado_actual': 'Preñada',
        })
        self.assertEqual(response.status_code, 201)
        preniez_id = response.json()['preniez']['id']
        response = self.client.post(reverse('finalizar_preniez', args=[preniez_id]), {
            'fecha': '2026-12-01', 'vivo': 'true',
        })
        self.assertEqual(response.status_code, 201)

        response = self.client.get(reverse('prenieces'))
        page_data = response.context['page_data']
        self.assertEqual(page_data['kpis']['partos_anio'], 1)
        parto = page_data['partos'][0]
        self.assertEqual(parto['vivo'], True)
        self.assertEqual(parto['madre_tipo'], 'Bovino')
        self.assertEqual(parto['tipo_preñez'], 'Natural')
        self.assertEqual(parto['crias'], [])


class InseminacionModuleTests(TestCase):
    def setUp(self):
        self.vaca1 = Animal.objects.create(
            id_senasa=90001, nombre='Vaca Uno', tipo_animal='Bovino', sexo='Hembra', vivo=True,
        )
        self.vaca2 = Animal.objects.create(
            id_senasa=90002, nombre='Vaca Dos', tipo_animal='Bovino', sexo='Hembra', vivo=True,
        )
        self.toro = Animal.objects.create(
            id_senasa=90003, nombre='Toro Insemina', tipo_animal='Bovino', sexo='Macho', vivo=True,
        )

    def crear_evento(self, animales=None, estado='false', costo=''):
        return self.client.post(reverse('crear_evento_inseminacion'), {
            'fecha_aplicacion': '2026-08-06',
            'estado': estado,
            'tipo_animal': 'Bovino',
            'padre_id': self.toro.idAnimal,
            'costo_total': costo,
            'animales': animales or [self.vaca1.idAnimal, self.vaca2.idAnimal],
        })

    def test_agendar_inseminacion_multiple(self):
        response = self.crear_evento()
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertEqual(evento.tipo, 'Inseminación')
        self.assertFalse(evento.estado)
        self.assertEqual(evento.padre, self.toro)
        self.assertEqual(evento.detalles.count(), 2)
        self.assertEqual(response.json()['evento']['total_hembras'], 2)

    def test_solo_hembras_y_padre_macho(self):
        response = self.client.post(reverse('crear_evento_inseminacion'), {
            'fecha_aplicacion': '2026-08-06', 'estado': 'true', 'tipo_animal': 'Bovino',
            'padre_id': self.toro.idAnimal, 'animales': [self.toro.idAnimal],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('hembra', response.json()['error'].lower())

        response = self.client.post(reverse('crear_evento_inseminacion'), {
            'fecha_aplicacion': '2026-08-06', 'estado': 'true', 'tipo_animal': 'Bovino',
            'padre_id': self.vaca1.idAnimal, 'animales': [self.vaca1.idAnimal],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('macho', response.json()['error'].lower())

    def test_inseminacion_exige_mismo_tipo_de_animal(self):
        oveja = Animal.objects.create(
            id_senasa=90004, nombre='Oveja Insemina', tipo_animal='Ovino', sexo='Hembra', vivo=True,
        )
        response = self.client.post(reverse('crear_evento_inseminacion'), {
            'fecha_aplicacion': '2026-08-06', 'estado': 'true', 'tipo_animal': 'Bovino',
            'padre_id': self.toro.idAnimal, 'animales': [oveja.idAnimal],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('tipo', response.json()['error'].lower())

        response = self.client.post(reverse('crear_evento_inseminacion'), {
            'fecha_aplicacion': '2026-08-06', 'estado': 'true', 'tipo_animal': 'Bovino',
            'padre_id': self.toro.idAnimal, 'animales': [self.vaca1.idAnimal],
        })
        self.assertEqual(response.status_code, 201)

    def test_inseminacion_requiere_tipo_animal(self):
        response = self.client.post(reverse('crear_evento_inseminacion'), {
            'fecha_aplicacion': '2026-08-06', 'estado': 'true',
            'padre_id': self.toro.idAnimal, 'animales': [self.vaca1.idAnimal],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('tipo', response.json()['error'].lower())

    def test_registrar_preniadas_desde_el_evento(self):
        evento_id = self.crear_evento(estado='true', costo='1500.00').json()['evento']['id']
        response = self.client.post(reverse('registrar_preniadas', args=[evento_id]), {
            'animales': [self.vaca1.idAnimal],
        })
        self.assertEqual(response.status_code, 201)
        preniez = Preniez.objects.get(madre=self.vaca1)
        self.assertEqual(preniez.tipo, 'Inseminación')
        self.assertEqual(preniez.estado_actual, 'Preñada')
        self.assertEqual(preniez.padre, self.toro)
        self.assertEqual(preniez.evento_sanitario_id, evento_id)
        self.assertEqual(preniez.fecha.isoformat(), '2026-08-06')
        # El egreso financiero lo genera el evento, no la preñez.
        self.assertEqual(MovimientoFinanciero.objects.count(), 1)
        self.assertEqual(response.json()['evento']['preñadas'], 1)

    def test_no_duplica_preniada_y_permite_varias(self):
        evento_id = self.crear_evento().json()['evento']['id']
        self.assertEqual(self.client.post(reverse('registrar_preniadas', args=[evento_id]), {
            'animales': [self.vaca1.idAnimal],
        }).status_code, 201)
        response = self.client.post(reverse('registrar_preniadas', args=[evento_id]), {
            'animales': [self.vaca1.idAnimal, self.vaca2.idAnimal],
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Preniez.objects.count(), 2)
        self.assertEqual(response.json()['evento']['preñadas'], 2)

    def test_parto_no_rehabilita_la_vaca_para_el_mismo_evento(self):
        # Tras registrar el parto, la hembra no debe poder volver a marcarse
        # como preñada en el mismo evento de inseminación.
        evento_id = self.crear_evento().json()['evento']['id']
        self.client.post(reverse('registrar_preniadas', args=[evento_id]), {
            'animales': [self.vaca1.idAnimal],
        })
        preniez = Preniez.objects.get(madre=self.vaca1)

        # Registrar el parto de esa preñez.
        response = self.client.post(reverse('finalizar_preniez', args=[preniez.id]), {
            'fecha': '2027-05-06', 'vivo': 'true',
        })
        self.assertEqual(response.status_code, 201)

        # La hembra sigue contando como preñada del evento.
        evento = EventoSanitario.objects.get(pk=evento_id)
        data = _evento_inseminacion_data(evento)
        self.assertEqual(data['preñadas'], 1)
        self.assertEqual(data['animales'][0]['preniada'], True)
        self.assertEqual(data['animales'][0]['de_este_evento'], True)

        # Intentar marcarla de nuevo no crea una segunda preñez.
        response = self.client.post(reverse('registrar_preniadas', args=[evento_id]), {
            'animales': [self.vaca1.idAnimal],
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Preniez.objects.filter(madre=self.vaca1).count(), 1)
        self.assertEqual(response.json()['evento']['preñadas'], 1)

    def test_evento_aplicado_genera_egreso_financiero(self):
        evento_id = self.crear_evento(estado='true', costo='1500.00').json()['evento']['id']
        evento = EventoSanitario.objects.get(pk=evento_id)
        self.assertIsNotNone(evento.mov_financiero)
        self.assertEqual(evento.mov_financiero.tipo, 'Egreso')
        self.assertEqual(evento.mov_financiero.monto_total, Decimal('1500.00'))

    def test_parto_y_cria_con_padre_por_defecto(self):
        evento_id = self.crear_evento().json()['evento']['id']
        self.client.post(reverse('registrar_preniadas', args=[evento_id]), {'animales': [self.vaca1.idAnimal]})
        preniez = Preniez.objects.get(madre=self.vaca1)

        response = self.client.post(reverse('finalizar_preniez', args=[preniez.id]), {
            'fecha': '2027-05-06', 'vivo': 'true',
        })
        self.assertEqual(response.status_code, 201)
        parto_id = response.json()['parto']['id']

        response = self.client.post(reverse('crear_animal'), {
            'tipo_animal': 'Bovino', 'sexo': 'Hembra', 'nombre': 'Cría inseminada',
            'madre_id': self.vaca1.idAnimal, 'padre_id': self.toro.idAnimal,
            'fecha_nacimiento': '2027-05-06', 'parto_id': parto_id,
            'movimiento_tipo': 'Nacimiento', 'movimiento_fecha': '2027-05-06',
        })
        self.assertEqual(response.status_code, 201)
        cria = Animal.objects.get(nombre='Cría inseminada')
        self.assertEqual(cria.madre, self.vaca1)
        self.assertEqual(cria.padre, self.toro)
        self.assertEqual(cria.tipo_animal, 'Bovino')

    def test_cambiar_caravana_desde_stock_no_desvincula_la_cria_del_parto(self):
        evento_id = self.crear_evento().json()['evento']['id']
        self.client.post(reverse('registrar_preniadas', args=[evento_id]), {'animales': [self.vaca1.idAnimal]})
        preniez = Preniez.objects.get(madre=self.vaca1)
        parto_id = self.client.post(reverse('finalizar_preniez', args=[preniez.id]), {
            'fecha': '2027-05-06', 'vivo': 'true',
        }).json()['parto']['id']
        cria_id = self.client.post(reverse('crear_animal'), {
            'tipo_animal': 'Bovino', 'sexo': 'Hembra', 'nombre': 'Cría con caravana',
            'id_senasa': '77777', 'madre_id': self.vaca1.idAnimal, 'padre_id': self.toro.idAnimal,
            'fecha_nacimiento': '2027-05-06', 'parto_id': parto_id,
            'movimiento_tipo': 'Nacimiento', 'movimiento_fecha': '2027-05-06',
        }).json()['id']

        # Cambio de caravana desde Stock (endpoint de edición, sin parto_id)
        response = self.client.post(reverse('actualizar_animal', args=[cria_id]), {
            'id_senasa': '99999', 'tipo_animal': 'Bovino', 'sexo': 'Hembra',
            'nombre': 'Cría con caravana', 'madre_id': self.vaca1.idAnimal,
        })
        self.assertEqual(response.status_code, 200)
        cria = Animal.objects.get(pk=cria_id)
        self.assertEqual(cria.id_senasa, 99999)
        self.assertEqual(cria.parto_id, parto_id)

        # La cría sigue figurando en el módulo de Preñez
        page_data = self.client.get(reverse('prenieces')).context['page_data']
        crias = [c for p in page_data['prenieces'] for c in p['crias']]
        self.assertTrue(any(c['id'] == cria_id for c in crias))

    def test_no_elimina_evento_con_preniadas(self):
        evento_id = self.crear_evento().json()['evento']['id']
        self.client.post(reverse('registrar_preniadas', args=[evento_id]), {'animales': [self.vaca1.idAnimal]})
        response = self.client.post(reverse('eliminar_evento_inseminacion', args=[evento_id]))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(EventoSanitario.objects.filter(pk=evento_id).exists())

    def test_pagina_incluye_eventos_inseminacion(self):
        response = self.client.get(reverse('prenieces'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('eventos_inseminacion', response.context['page_data'])
        self.assertEqual(response.context['page_data']['eventos_inseminacion'], [])
