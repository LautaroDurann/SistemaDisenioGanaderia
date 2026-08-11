import base64
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from animales.models import Animal, Parto, Preniez
from establecimientos.models import Establecimiento, Parcela
from finanzas.models import Compra, LiquidacionSueldo, MovimientoFinanciero, Venta
from inventario.models import Consumo, DetalleCompra, Insumo, Lote
from sanidad.models import DetalleEvento, EventoSanitario, Enfermedad, Diagnostico
from web.views import _evento_inseminacion_data
from web.models import Notificacion
from usuarios.models import Comprador, Persona, Proveedor, RolEstablecimiento, Usuario


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
        persona = Persona.objects.create(
            nombre='Juan', apellido='Fernandez', correo_electronico='juan@test.com',
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

    def test_paginas_principales_responden(self):
        for url_name in ('dashboard', 'stock', 'movimientos', 'parcelas', 'vacunacion', 'sanidad', 'alimentacion', 'usuarios', 'configuracion', 'prenieces'):
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_navbar_no_ofrece_todos_los_establecimientos(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Todos los establecimientos')
        self.assertContains(response, 'Campo de prueba')

    def test_pagina_usuarios_incluye_datos_huacapp(self):
        response = self.client.get(reverse('usuarios'))
        self.assertContains(response, 'huacapp-data-usuarios')
        self.assertContains(response, 'huacapp-data-establecimientos')
        self.assertContains(response, 'window.HUACAPP_DATA')
        self.assertContains(response, 'propietario')
        self.assertContains(response, 'Campo de prueba')
        contenido = response.content.decode()
        inicio = contenido.index('id="huacapp-data-establecimientos"') 
        inicio = contenido.index('>', inicio) + 1
        fin = contenido.index('</script>', inicio)
        establecimientos = json.loads(contenido[inicio:fin])
        self.assertEqual([e['nombre'] for e in establecimientos], ['Campo de prueba'])

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
        self.assertEqual(MovimientoFinanciero.objects.filter(activo=True).count(), 0)

    def test_eliminar_evento_con_costo_elimina_el_movimiento_financiero(self):
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'true',
            'costo_total': '5000.00', 'animal_id': self.animal.idAnimal,
        })
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertEqual(MovimientoFinanciero.objects.count(), 1)

        response = self.client.post(reverse('eliminar_evento_sanitario', args=[evento.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventoSanitario.objects.filter(pk=evento.id, activo=True).exists())
        self.assertEqual(MovimientoFinanciero.objects.filter(activo=True).count(), 0)

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

    def test_api_stock(self):
        response = self.client.get(reverse('stock_api'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['animales'][0]['caravana'], '12345')

    def test_filtro_madre_incluye_todas_las_hembras_con_crias(self):
        # Madre con cría registrada: debe aparecer aunque esté muerta/vendida.
        madre = Animal.objects.create(id_senasa='20001', nombre='Mama', tipo_animal='Bovino', sexo='Hembra', parcela=self.parcela, vivo=False)
        Animal.objects.create(id_senasa='20002', nombre='Cria', tipo_animal='Bovino', sexo='Hembra', parcela=self.parcela, madre=madre, vivo=True)
        # Hembra sin crías: no debe aparecer.
        Animal.objects.create(id_senasa='20003', nombre='Sola', tipo_animal='Bovino', sexo='Hembra', parcela=self.parcela, vivo=True)
        # Macho con crías: no debe aparecer.
        toro = Animal.objects.create(id_senasa='20004', nombre='Toro', tipo_animal='Bovino', sexo='Macho', parcela=self.parcela, vivo=True)
        Animal.objects.create(id_senasa='20005', nombre='Cria toro', tipo_animal='Bovino', sexo='Hembra', parcela=self.parcela, padre=toro, vivo=True)

        response = self.client.get(reverse('stock'))
        self.assertEqual(response.status_code, 200)
        ids = {m['id'] for m in response.context['page_data']['madres']}
        self.assertEqual(ids, {madre.idAnimal})

    def test_madre_de_distinto_tipo_rechazada(self):
        madre_ovino = Animal.objects.create(id_senasa='30001', nombre='Oveja', tipo_animal='Ovino', sexo='Hembra', parcela=self.parcela, vivo=True)
        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': '30002', 'nombre': 'Cordero', 'sexo': 'Macho', 'tipo_animal': 'Bovino',
            'madre_id': madre_ovino.idAnimal,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Animal.objects.filter(id_senasa='30002').exists())

    def test_padre_de_distinto_tipo_rechazado(self):
        padre_ovino = Animal.objects.create(id_senasa='30003', nombre='Carnero', tipo_animal='Ovino', sexo='Macho', parcela=self.parcela, vivo=True)
        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': '30004', 'nombre': 'Cordero', 'sexo': 'Hembra', 'tipo_animal': 'Bovino',
            'padre_id': padre_ovino.idAnimal,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Animal.objects.filter(id_senasa='30004').exists())

    def test_crear_animal_desde_stock(self):
        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': '67890', 'nombre': 'Mora', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'raza': 'Angus', 'peso_actual': '285.00', 'parcela_id': self.parcela.id,
        })
        self.assertEqual(response.status_code, 201)
        animal = Animal.objects.get(id_senasa=67890)
        self.assertEqual(animal.parcela, self.parcela)
        self.assertEqual(str(animal.peso_actual), '285.00')

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
        self.assertFalse(Animal.objects.filter(pk=self.animal.idAnimal, activo=True).exists())

    def test_crear_animal_con_caravana_alfanumerica(self):
        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': 'AR2500X7', 'nombre': 'Mora', 'sexo': 'Hembra', 'tipo_animal': 'Bovino',
        })
        self.assertEqual(response.status_code, 201)
        animal = Animal.objects.get(id_senasa='AR2500X7')
        self.assertEqual(animal.id_senasa, 'AR2500X7')

    def test_crear_animal_caravana_con_simbolos_rechazada(self):
        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': 'AR25%#', 'nombre': 'Mora', 'sexo': 'Hembra', 'tipo_animal': 'Bovino',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Animal.objects.filter(id_senasa='AR25%#').exists())

    def test_marcar_animal_muerto_guarda_fecha_muerte(self):
        response = self.client.post(reverse('actualizar_animal', args=[self.animal.idAnimal]), {
            'id_senasa': '12345', 'nombre': 'Luna', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'fecha_nacimiento': '2020-03-01',
            'fecha_muerte': '2026-07-15',
        })
        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertFalse(self.animal.vivo)
        self.assertEqual(self.animal.fecha_muerte, date(2026, 7, 15))

    def test_animal_vivo_limpia_fecha_muerte(self):
        self.animal.vivo = False
        self.animal.fecha_muerte = date(2026, 7, 15)
        self.animal.save()
        response = self.client.post(reverse('actualizar_animal', args=[self.animal.idAnimal]), {
            'id_senasa': '12345', 'nombre': 'Luna', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'vivo': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertTrue(self.animal.vivo)
        self.assertIsNone(self.animal.fecha_muerte)

    def test_fecha_muerte_anterior_al_nacimiento_rechazada(self):
        response = self.client.post(reverse('actualizar_animal', args=[self.animal.idAnimal]), {
            'id_senasa': '12345', 'nombre': 'Luna', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'fecha_nacimiento': '2020-03-01',
            'fecha_muerte': '2019-01-01',
        })
        self.assertEqual(response.status_code, 400)

    def test_editar_animal_conserva_compra_y_venta_asociadas(self):
        compra = Compra.objects.create(tipo='Animales', fecha='2026-08-01', monto_total=Decimal('500000.00'))
        venta = Venta.objects.create(
            tipo='Animales', fecha='2026-08-01', peso_total=Decimal('400.00'),
            precio_por_kg=Decimal('1000.00'), monto_total=Decimal('396000.00'),
        )
        self.animal.compra = compra
        self.animal.venta = venta
        self.animal.costo_adquisicion = Decimal('500000.00')
        self.animal.precio_venta = Decimal('396000.00')
        self.animal.save()

        response = self.client.post(reverse('actualizar_animal', args=[self.animal.idAnimal]), {
            'id_senasa': '12345', 'nombre': 'Luna editada', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'peso_actual': '420.00',
        })
        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.nombre, 'Luna editada')
        self.assertEqual(self.animal.compra, compra)
        self.assertEqual(self.animal.venta, venta)
        self.assertEqual(self.animal.costo_adquisicion, Decimal('500000.00'))
        self.assertEqual(self.animal.precio_venta, Decimal('396000.00'))

    def test_crear_parcela(self):
        response = self.client.post(reverse('crear_parcela'), {
            'ancho': '15', 'largo': '40', 'descripcion': 'Parcela nueva', 'estado': 'En pastoreo',
        })
        self.assertEqual(response.status_code, 201)
        parcela = Parcela.objects.get(descripcion='Parcela nueva')
        self.assertEqual(parcela.estado, 'En pastoreo')

    def test_crear_parcela_sin_establecimiento_crea_uno_por_defecto(self):
        Establecimiento.objects.all().delete()
        response = self.client.post(reverse('crear_parcela'), {
            'ancho': '10', 'largo': '20', 'descripcion': 'Parcela nueva', 'estado': 'En descanso',
        })
        self.assertEqual(response.status_code, 201)
        parcela = Parcela.objects.get(descripcion='Parcela nueva')
        self.assertEqual(parcela.estado, 'En descanso')
        self.assertTrue(Establecimiento.objects.filter(nombre='Establecimiento principal').exists())

    def test_actualizar_parcela(self):
        response = self.client.post(reverse('crear_parcela'), {
            'id': self.parcela.id, 'ancho': '25', 'largo': '50', 'descripcion': 'Parcela editada', 'estado': 'En descanso',
        })
        self.assertEqual(response.status_code, 200)
        self.parcela.refresh_from_db()
        self.assertEqual(self.parcela.estado, 'En descanso')
        self.assertEqual(self.parcela.ancho, Decimal('25'))
        self.assertEqual(self.parcela.largo, Decimal('50'))

    def test_eliminar_parcela(self):
        response = self.client.post(reverse('eliminar_parcela', args=[self.parcela.id]))
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
        self.assertFalse(Venta.objects.filter(activo=True).exists())
        self.assertFalse(MovimientoFinanciero.objects.filter(activo=True).exists())

    def test_actualizar_venta_recalcula_montos_y_conserva_animales(self):
        self.animal.peso_actual = Decimal('300.00')
        self.animal.save(update_fields=['peso_actual'])
        segundo = Animal.objects.create(
            id_senasa=54323, nombre='Toro', tipo_animal='Bovino', sexo='Macho',
            peso_actual=Decimal('500.00'), parcela=self.parcela, vivo=True,
        )
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-03', 'tipo': 'Venta de hacienda', 'precio_por_kg': '2500.50',
            'detalle': 'Venta de prueba', 'animales': [self.animal.idAnimal, segundo.idAnimal],
        })
        venta = Venta.objects.get(pk=response.json()['id'])
        self.assertEqual(venta.monto_total, Decimal('2000400.00'))

        response = self.client.post(reverse('actualizar_venta', args=[venta.id]), {
            'fecha': '2026-08-10', 'precio_por_kg': '3000.00', 'peso_total': '700.00',
            'peso_manual': 'on', 'estadoDeCobro': 'Pagada', 'metodoDePago': 'Transferencia',
            'detalle': 'Venta editada', 'animales': [self.animal.idAnimal, segundo.idAnimal],
        })
        self.assertEqual(response.status_code, 200)
        venta.refresh_from_db()
        self.assertEqual(venta.precio_por_kg, Decimal('3000.00'))
        self.assertEqual(venta.peso_total, Decimal('700.00'))
        self.assertEqual(venta.monto_total, Decimal('2100000.00'))
        self.assertEqual(venta.estadoDeCobro, 'Pagada')
        self.assertEqual(venta.mov_financiero.monto_total, Decimal('2100000.00'))
        self.animal.refresh_from_db()
        self.assertTrue(self.animal.vendido)
        self.assertEqual(self.animal.venta, venta)
        self.assertEqual(self.animal.precio_venta, Decimal('1050000.00'))

    def test_editar_venta_cambiar_animales_restaura_el_stock(self):
        self.animal.peso_actual = Decimal('300.00')
        self.animal.save(update_fields=['peso_actual'])
        segundo = Animal.objects.create(
            id_senasa=54324, nombre='Toro', tipo_animal='Bovino', sexo='Macho',
            peso_actual=Decimal('500.00'), parcela=self.parcela, vivo=True,
        )
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-03', 'precio_por_kg': '1000.00', 'peso_total': '800.00',
            'peso_manual': 'on', 'animales': [self.animal.idAnimal, segundo.idAnimal],
        })
        venta = Venta.objects.get(pk=response.json()['id'])
        segundo.refresh_from_db()
        self.assertTrue(segundo.vendido)

        response = self.client.post(reverse('actualizar_venta', args=[venta.id]), {
            'fecha': '2026-08-03', 'precio_por_kg': '1000.00', 'peso_total': '300.00',
            'peso_manual': 'on', 'animales': [self.animal.idAnimal],
        })
        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        segundo.refresh_from_db()
        self.assertTrue(self.animal.vendido)
        self.assertEqual(self.animal.venta, venta)
        self.assertFalse(segundo.vendido)
        self.assertIsNone(segundo.venta)

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

    def test_venta_con_porcentaje_de_desbaste_calcula_peso_neto_y_monto(self):
        establecimiento = self.animal.parcela.establecimiento
        self.animal.peso_actual = Decimal('300.00')
        self.animal.establecimiento = establecimiento
        self.animal.save(update_fields=['peso_actual', 'establecimiento'])
        segundo = Animal.objects.create(
            id_senasa=54322, nombre='Toro 2', tipo_animal='Bovino', sexo='Macho',
            peso_actual=Decimal('500.00'), parcela=self.parcela,
            establecimiento=establecimiento, vivo=True,
        )
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-05', 'tipo': 'Venta de hacienda', 'precio_por_kg': '100.00',
            'porcentajeDesbaste': '10', 'detalle': 'Venta con desbaste',
            'animales': [self.animal.idAnimal, segundo.idAnimal],
        })
        self.assertEqual(response.status_code, 201)
        venta = Venta.objects.get(pk=response.json()['id'])
        self.assertEqual(venta.peso_total, Decimal('800.00'))
        self.assertEqual(venta.porcentajeDesbaste, Decimal('10.00'))
        self.assertEqual(venta.peso_desbastado, Decimal('720.00'))
        self.assertEqual(venta.monto_total, Decimal('72000.00'))
        self.assertEqual(venta.mov_financiero.monto_total, Decimal('72000.00'))
        self.animal.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(self.animal.precio_venta, Decimal('27000.00'))
        self.assertEqual(segundo.precio_venta, Decimal('45000.00'))

        payload = response.json()['venta']
        self.assertEqual(payload['porcentaje_desbaste'], '10.00')
        self.assertEqual(payload['peso_desbastado'], '720.00')

        page = self.client.get(reverse('ventas'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, '720.00')
        self.assertContains(page, 'Peso neto')

    def test_venta_con_desbaste_y_peso_manual(self):
        self.animal.peso_actual = None
        self.animal.save(update_fields=['peso_actual'])
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-06', 'tipo': 'Venta de prueba', 'precio_por_kg': '1500.00',
            'peso_total': '420.00', 'peso_manual': 'on', 'porcentajeDesbaste': '5',
            'animales': [self.animal.idAnimal],
        })
        self.assertEqual(response.status_code, 201)
        venta = Venta.objects.get(pk=response.json()['id'])
        self.assertEqual(venta.peso_total, Decimal('420.00'))
        self.assertEqual(venta.peso_desbastado, Decimal('399.00'))
        self.assertEqual(venta.monto_total, Decimal('598500.00'))
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.precio_venta, Decimal('598500.00'))

    def test_venta_rechaza_porcentaje_de_desbaste_invalido(self):
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-07', 'tipo': 'Venta de prueba', 'precio_por_kg': '100.00',
            'porcentajeDesbaste': '150', 'animales': [self.animal.idAnimal],
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Venta.objects.exists())

        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-07', 'tipo': 'Venta de prueba', 'precio_por_kg': '100.00',
            'porcentajeDesbaste': '-5', 'animales': [self.animal.idAnimal],
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Venta.objects.exists())

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
        self.assertFalse(Comprador.objects.filter(pk=comprador.id, activo=True).exists())


class CompraModuleTests(TestCase):
    def setUp(self):
        establecimiento = Establecimiento.objects.create(
            nombre='Campo de prueba', fecha_inicio=date.today(), ubicacion='Córdoba'
        )
        proveedor = Proveedor.objects.create(
            nombre='Carlos', apellido='Lopez', correo_electronico='carlos@proveedor.com',
            fecha_nacimiento='1980-05-10',
        )
        self.proveedor = proveedor
        persona = Persona.objects.create(
            nombre='Juan', apellido='Fernandez', correo_electronico='juan@test.com',
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
        session['establecimiento_id'] = establecimiento.id
        session.save()

    def crear_compra(self, datos):
        return self.client.post(reverse('crear_compra'), datos)

    def test_pagina_compras_responde(self):
        response = self.client.get(reverse('compras'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'window.HUACAPP_DATA')
        self.assertContains(response, 'Carlos')

    def test_compra_de_insumos_crea_lote_detalle_y_movimiento(self):
        response = self.crear_compra({
            'tipo': 'Insumos', 'fecha': '2026-08-01', 'proveedor_id': self.proveedor.id,
            'insumo_id': '', 'nuevo_insumo': 'Vacuna aftosa', 'tipo_insumo': 'Vacuna',
            'lote_nombre': 'Lote Aftosa', 'fecha_vencimiento': '2027-08-01',
            'cantidad': '50', 'precio_unitario': '120.50',
        })
        self.assertEqual(response.status_code, 201)
        compra = Compra.objects.get(pk=response.json()['id'])
        self.assertEqual(compra.tipo, 'Insumos')
        self.assertEqual(compra.monto_total, Decimal('6025.00'))
        self.assertEqual(compra.proveedor, self.proveedor)

        insumo = Insumo.objects.get(nombre='Vacuna aftosa')
        lote = Lote.objects.get(insumo=insumo)
        detalle = DetalleCompra.objects.get(compra=compra)
        self.assertEqual(detalle.lote, lote)
        self.assertEqual(detalle.cantidad, Decimal('50.00'))
        self.assertEqual(detalle.precioUnitario, Decimal('120.50'))
        self.assertEqual(lote.stockActual, Decimal('50.00'))
        self.assertEqual(lote.nombre, 'Lote Aftosa')

        movimiento = compra.mov_financiero
        self.assertIsNotNone(movimiento)
        self.assertEqual(movimiento.tipo, 'Egreso')
        self.assertEqual(movimiento.monto_total, Decimal('6025.00'))
        self.assertIn('Vacuna aftosa', movimiento.detalle)

    def test_compra_de_animal_crea_animal_vinculado_y_movimiento(self):
        response = self.crear_compra({
            'tipo': 'Animales', 'fecha': '2026-08-01', 'proveedor_id': self.proveedor.id,
            'id_senasa': '99911', 'nombre': 'Toro comprado', 'tipo_animal': 'Bovino',
            'sexo': 'Macho', 'raza': 'Angus', 'color': 'Negro',
            'peso_al_nacer': '40', 'peso_actual': '320', 'monto_total': '850000',
            'costo_adquisicion': '850000', 'descripcion': 'Comprado en remate',
        })
        self.assertEqual(response.status_code, 201)
        compra = Compra.objects.get(pk=response.json()['id'])
        animal = Animal.objects.get(compra=compra)
        self.assertEqual(animal.id_senasa, '99911')
        self.assertEqual(animal.nombre, 'Toro comprado')
        self.assertEqual(animal.sexo, 'Macho')
        self.assertEqual(animal.costo_adquisicion, Decimal('850000.00'))
        self.assertEqual(animal.establecimiento.nombre, 'Campo de prueba')
        self.assertIsNone(animal.diametro_escrotal)
        self.assertTrue(animal.vivo)

        movimiento = compra.mov_financiero
        self.assertIsNotNone(movimiento)
        self.assertEqual(movimiento.tipo, 'Egreso')
        self.assertEqual(movimiento.monto_total, Decimal('850000.00'))
        self.assertIn('Toro comprado', movimiento.detalle)

    def test_compra_de_animal_no_exige_diametro_escrotal(self):
        response = self.crear_compra({
            'tipo': 'Animales', 'fecha': '2026-08-01', 'tipo_animal': 'Bovino',
            'sexo': 'Macho', 'nombre': 'Sin diametro', 'monto_total': '500000',
            'costo_adquisicion': '500000',
        })
        self.assertEqual(response.status_code, 201)
        animal = Animal.objects.get(compra=Compra.objects.get(pk=response.json()['id']))
        self.assertIsNone(animal.diametro_escrotal)

    def test_editar_compra_de_animal_conserva_diametro_cargado_en_animales(self):
        response = self.crear_compra({
            'tipo': 'Animales', 'fecha': '2026-08-01', 'tipo_animal': 'Bovino',
            'sexo': 'Macho', 'nombre': 'Toro', 'monto_total': '500000', 'costo_adquisicion': '500000',
        })
        compra = Compra.objects.get(pk=response.json()['id'])
        animal = Animal.objects.get(compra=compra)
        # El diámetro se carga después, desde el módulo de Animales.
        animal.diametro_escrotal = Decimal('34.50')
        animal.save(update_fields=['diametro_escrotal'])

        response = self.client.post(reverse('actualizar_compra', args=[compra.id]), {
            'tipo': 'Animales', 'fecha': '2026-08-02', 'tipo_animal': 'Bovino',
            'sexo': 'Macho', 'nombre': 'Toro', 'monto_total': '600000', 'costo_adquisicion': '600000',
        })
        self.assertEqual(response.status_code, 200)
        animal.refresh_from_db()
        compra.refresh_from_db()
        self.assertEqual(animal.diametro_escrotal, Decimal('34.50'))
        self.assertEqual(compra.monto_total, Decimal('600000.00'))
        self.assertEqual(compra.mov_financiero.monto_total, Decimal('600000.00'))

    def test_compra_generica_sin_lote_ni_animal(self):
        response = self.crear_compra({
            'tipo': 'Maquinaria', 'fecha': '2026-08-01', 'proveedor_id': self.proveedor.id,
            'monto_total': '300000', 'detalle': 'Tractor',
        })
        self.assertEqual(response.status_code, 201)
        compra = Compra.objects.get(pk=response.json()['id'])
        self.assertEqual(compra.monto_total, Decimal('300000.00'))
        self.assertEqual(compra.detalles.count(), 0)
        self.assertEqual(compra.animal_set.count(), 0)
        self.assertEqual(compra.mov_financiero.monto_total, Decimal('300000.00'))

    def test_cambiar_tipo_de_insumos_a_generica_quita_el_lote(self):
        response = self.crear_compra({
            'tipo': 'Insumos', 'fecha': '2026-08-01', 'nuevo_insumo': 'Antiparasitario',
            'tipo_insumo': 'Medicamento', 'cantidad': '10', 'precio_unitario': '50',
        })
        compra = Compra.objects.get(pk=response.json()['id'])
        self.assertEqual(compra.detalles.count(), 1)

        response = self.client.post(reverse('actualizar_compra', args=[compra.id]), {
            'tipo': 'Otros', 'fecha': '2026-08-01', 'monto_total': '500',
        })
        self.assertEqual(response.status_code, 200)
        compra.refresh_from_db()
        self.assertEqual(compra.detalles.count(), 0)
        self.assertEqual(Lote.objects.filter(insumo__nombre='Antiparasitario').count(), 0)

    def test_cambiar_tipo_de_animales_a_generica_quita_el_animal(self):
        response = self.crear_compra({
            'tipo': 'Animales', 'fecha': '2026-08-01', 'tipo_animal': 'Bovino',
            'sexo': 'Macho', 'nombre': 'Toro', 'monto_total': '500000', 'costo_adquisicion': '500000',
        })
        compra = Compra.objects.get(pk=response.json()['id'])
        animal = Animal.objects.get(compra=compra)

        response = self.client.post(reverse('actualizar_compra', args=[compra.id]), {
            'tipo': 'Otros', 'fecha': '2026-08-01', 'monto_total': '500',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Animal.objects.filter(pk=animal.pk).exists())

    def test_eliminar_compra_elimina_movimiento_y_efectos(self):
        response = self.crear_compra({
            'tipo': 'Insumos', 'fecha': '2026-08-01', 'nuevo_insumo': 'Vacuna',
            'tipo_insumo': 'Vacuna', 'cantidad': '10', 'precio_unitario': '50',
        })
        compra = Compra.objects.get(pk=response.json()['id'])
        movimiento_id = compra.mov_financiero_id
        lote_id = compra.detalles.first().lote_id

        response = self.client.post(reverse('eliminar_compra', args=[compra.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Compra.objects.filter(pk=compra.id, activo=True).exists())
        self.assertFalse(MovimientoFinanciero.objects.filter(pk=movimiento_id, activo=True).exists())
        self.assertTrue(Lote.objects.filter(pk=lote_id).exists())

    def test_compra_de_insumos_sin_cantidad_da_error(self):
        response = self.crear_compra({
            'tipo': 'Insumos', 'fecha': '2026-08-01', 'cantidad': '', 'precio_unitario': '50',
        })
        self.assertEqual(response.status_code, 400)

    def test_compra_de_animal_sin_monto_da_error(self):
        response = self.crear_compra({
            'tipo': 'Animales', 'fecha': '2026-08-01', 'tipo_animal': 'Bovino', 'sexo': 'Macho',
        })
        self.assertEqual(response.status_code, 400)


class FinanzasSyncTests(TestCase):
    def setUp(self):
        establecimiento = Establecimiento.objects.create(
            nombre='Campo de prueba', fecha_inicio=date.today(), ubicacion='Córdoba'
        )
        self.establecimiento = establecimiento
        proveedor = Proveedor.objects.create(
            nombre='Carlos', apellido='Lopez', correo_electronico='carlos@proveedor.com',
            fecha_nacimiento='1980-05-10',
        )
        self.proveedor = proveedor
        persona = Persona.objects.create(
            nombre='Juan', apellido='Fernandez', correo_electronico='juan@test.com',
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
        session['establecimiento_id'] = establecimiento.id
        session.save()

    def test_pagina_finanzas_usa_decimal_para_kpis_js(self):
        response = self.client.get(reverse('finanzas'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('const KPI_INGRESOS = 0.00;', content)
        self.assertIn('const KPI_EGRESOS = 0.00;', content)
        self.assertIn('const KPI_BALANCE = 0.00;', content)

    def test_eliminar_movimiento_libre(self):
        response = self.client.post(reverse('api_finanzas_movimientos'), {
            'fecha': '2026-08-01', 'tipo': 'Ingreso', 'nombre': 'Venta de tambo',
            'monto_total': '1500', 'detalle': '',
        })
        self.assertEqual(response.status_code, 201)
        movimiento_id = response.json()['movimiento']['id']

        response = self.client.post(reverse('eliminar_movimiento_financiero', args=[movimiento_id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MovimientoFinanciero.objects.filter(pk=movimiento_id, activo=True).exists())

    def test_eliminar_movimiento_vinculado_a_venta_bloqueado(self):
        animal = Animal.objects.create(
            id_senasa=55511, nombre='Vaca venta', tipo_animal='Bovino', sexo='Hembra',
            vivo=True, peso_actual=Decimal('350'), establecimiento=self.establecimiento,
        )
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-01', 'precio_por_kg': '100', 'animales': [str(animal.idAnimal)],
            'peso_total': '350', 'peso_manual': 'on',
        })
        self.assertEqual(response.status_code, 201)
        venta = Venta.objects.get(pk=response.json()['id'])
        movimiento_id = venta.mov_financiero_id
        self.assertIsNotNone(movimiento_id)

        response = self.client.post(reverse('eliminar_movimiento_financiero', args=[movimiento_id]))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Venta.objects.filter(pk=venta.id).exists())
        animal.refresh_from_db()
        self.assertTrue(animal.vendido)
        self.assertEqual(animal.venta_id, venta.id)

    def test_eliminar_movimiento_vinculado_a_compra_bloqueado(self):
        response = self.client.post(reverse('crear_compra'), {
            'tipo': 'Insumos', 'fecha': '2026-08-01', 'proveedor_id': self.proveedor.id,
            'nuevo_insumo': 'Vacuna aftosa', 'tipo_insumo': 'Vacuna',
            'cantidad': '10', 'precio_unitario': '100',
        })
        self.assertEqual(response.status_code, 201)
        compra = Compra.objects.get(pk=response.json()['id'])
        movimiento_id = compra.mov_financiero_id

        response = self.client.post(reverse('eliminar_movimiento_financiero', args=[movimiento_id]))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Compra.objects.filter(pk=compra.id).exists())
        self.assertTrue(MovimientoFinanciero.objects.filter(pk=movimiento_id).exists())

    def get_page_data(self, url_name):
        response = self.client.get(reverse(url_name))
        content = response.content.decode()
        inicio = content.index('id="huacapp-page-data"')
        inicio = content.index('>', inicio) + 1
        fin = content.index('</script>', inicio)
        return response, json.loads(content[inicio:fin])

    def crear_animal_venta(self, id_senasa):
        return Animal.objects.create(
            id_senasa=id_senasa, nombre='Vaca venta', tipo_animal='Bovino', sexo='Hembra',
            vivo=True, peso_actual=Decimal('300'), establecimiento=self.establecimiento,
        )

    def test_venta_guarda_estado_de_cobro_y_metodo_de_pago(self):
        animal = self.crear_animal_venta(55520)
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-01', 'precio_por_kg': '100', 'animales': [str(animal.idAnimal)],
            'peso_total': '300', 'peso_manual': 'on',
            'estadoDeCobro': 'Pagada', 'metodoDePago': 'Transferencia',
        })
        self.assertEqual(response.status_code, 201)
        venta = Venta.objects.get(pk=response.json()['id'])
        self.assertEqual(venta.estadoDeCobro, 'Pagada')
        self.assertEqual(venta.metodoDePago, 'Transferencia')
        payload = response.json()['venta']
        self.assertEqual(payload['estado_de_cobro'], 'Pagada')
        self.assertEqual(payload['metodo_de_pago'], 'Transferencia')

    def test_compra_guarda_estado_de_pago_y_metodo_de_pago(self):
        response = self.client.post(reverse('crear_compra'), {
            'tipo': 'Otros', 'fecha': '2026-08-01', 'monto_total': '500',
            'estadoDePago': 'Pagada', 'metodoDePago': 'Cheque',
        })
        self.assertEqual(response.status_code, 201)
        compra = Compra.objects.get(pk=response.json()['id'])
        self.assertEqual(compra.estadoDePago, 'Pagada')
        self.assertEqual(compra.metodoDePago, 'Cheque')

    def test_venta_y_compra_usan_estados_por_defecto(self):
        animal = self.crear_animal_venta(55521)
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-01', 'precio_por_kg': '100', 'animales': [str(animal.idAnimal)],
            'peso_total': '300', 'peso_manual': 'on',
        })
        self.assertEqual(response.status_code, 201)
        venta = Venta.objects.get(pk=response.json()['id'])
        self.assertEqual(venta.estadoDeCobro, 'Pendiente')
        self.assertEqual(venta.metodoDePago, 'Efectivo')

        response = self.client.post(reverse('crear_compra'), {
            'tipo': 'Otros', 'fecha': '2026-08-01', 'monto_total': '500',
        })
        self.assertEqual(response.status_code, 201)
        compra = Compra.objects.get(pk=response.json()['id'])
        self.assertEqual(compra.estadoDePago, 'Pendiente')
        self.assertEqual(compra.metodoDePago, 'Efectivo')

    def test_venta_rechaza_estado_de_cobro_invalido(self):
        animal = self.crear_animal_venta(55522)
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-01', 'precio_por_kg': '100', 'animales': [str(animal.idAnimal)],
            'peso_total': '300', 'peso_manual': 'on', 'estadoDeCobro': 'Cobrado',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Venta.objects.exists())

    def test_compra_rechaza_metodo_de_pago_invalido(self):
        response = self.client.post(reverse('crear_compra'), {
            'tipo': 'Otros', 'fecha': '2026-08-01', 'monto_total': '500',
            'metodoDePago': 'Bitcoin',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Compra.objects.exists())

    def test_pagina_ventas_embebe_estado_y_resumen_del_mes(self):
        animal = self.crear_animal_venta(55523)
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-01', 'precio_por_kg': '100', 'animales': [str(animal.idAnimal)],
            'peso_total': '300', 'peso_manual': 'on',
            'estadoDeCobro': 'Pagada', 'metodoDePago': 'Cheque',
        })
        self.assertEqual(response.status_code, 201)
        response, data = self.get_page_data('ventas')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('resumen-anio-cantidad', content)
        self.assertIn('resumen-anio-ingresos', content)
        self.assertIn('resumen-anio-kilos', content)
        venta = data['ventas'][0]
        self.assertEqual(venta['estado_de_cobro'], 'Pagada')
        self.assertEqual(venta['metodo_de_pago'], 'Cheque')

    def test_pagina_compras_muestra_montos_por_tipo(self):
        response = self.client.post(reverse('crear_compra'), {
            'tipo': 'Insumos', 'fecha': '2026-08-01', 'nuevo_insumo': 'Vacuna aftosa',
            'tipo_insumo': 'Vacuna', 'cantidad': '10', 'precio_unitario': '100',
        })
        self.assertEqual(response.status_code, 201)
        response = self.client.post(reverse('crear_compra'), {
            'tipo': 'Maquinaria', 'fecha': '2026-08-02', 'monto_total': '500',
            'estadoDePago': 'Pendiente', 'metodoDePago': 'Transferencia',
        })
        self.assertEqual(response.status_code, 201)
        response, data = self.get_page_data('compras')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('montos-tipo-body', content)
        tipos = sorted(c['tipo'] for c in data['compras'])
        self.assertEqual(tipos, ['Insumos', 'Maquinaria'])
        maquinaria = next(c for c in data['compras'] if c['tipo'] == 'Maquinaria')
        self.assertEqual(maquinaria['estado_de_pago'], 'Pendiente')
        self.assertEqual(maquinaria['metodo_de_pago'], 'Transferencia')

    def test_pagina_finanzas_incluye_flujo_categorias_y_comparativa(self):
        animal = self.crear_animal_venta(55524)
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-01', 'precio_por_kg': '100', 'animales': [str(animal.idAnimal)],
            'peso_total': '300', 'peso_manual': 'on',
        })
        self.assertEqual(response.status_code, 201)
        response = self.client.post(reverse('crear_compra'), {
            'tipo': 'Insumos', 'fecha': '2026-08-01', 'nuevo_insumo': 'Vacuna aftosa',
            'tipo_insumo': 'Vacuna', 'cantidad': '10', 'precio_unitario': '100',
        })
        self.assertEqual(response.status_code, 201)
        response = self.client.post(reverse('api_finanzas_movimientos'), {
            'fecha': '2026-08-02', 'tipo': 'Egreso', 'nombre': 'Gasto general',
            'monto_total': '200', 'detalle': '',
        })
        self.assertEqual(response.status_code, 201)
        response, data = self.get_page_data('finanzas')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('chart-flujo', content)
        self.assertIn('chart-categorias', content)
        self.assertIn('chart-establecimientos', content)

        flujo = data['flujo']
        etiquetas = json.loads(flujo['etiquetas_json'])
        valores = json.loads(flujo['valores_json'])
        self.assertEqual(len(valores), 12)
        self.assertEqual(etiquetas, ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'])
        self.assertEqual(valores[:7], [0.0] * 7)
        self.assertEqual(valores[7], 28800.0)
        self.assertEqual(valores[-1], 28800.0)
        categorias = json.loads(data['categorias']['valores_json'])
        self.assertEqual(dict(zip(json.loads(data['categorias']['etiquetas_json']), categorias)),
                         {'Insumos': 1000.0, 'Gastos varios': 200.0})
        establecimientos = data['establecimientos']
        self.assertEqual(json.loads(establecimientos['etiquetas_json']), ['Campo de prueba'])
        self.assertEqual(json.loads(establecimientos['ingresos_json']), [30000.0])
        self.assertEqual(json.loads(establecimientos['egresos_json']), [1200.0])

    def test_eliminar_movimiento_vinculado_a_evento_bloqueado(self):
        animal = Animal.objects.create(
            id_senasa=55512, nombre='Vaca evento', tipo_animal='Bovino', sexo='Hembra', vivo=True,
        )
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'on',
            'costo_total': '2000', 'animal_id': str(animal.idAnimal),
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        movimiento_id = evento.mov_financiero_id
        self.assertIsNotNone(movimiento_id)

        response = self.client.post(reverse('eliminar_movimiento_financiero', args=[movimiento_id]))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(EventoSanitario.objects.filter(pk=evento.id).exists())

    def test_cambiar_tipo_compra_animal_con_preniez_conserva_animal(self):
        response = self.client.post(reverse('crear_compra'), {
            'tipo': 'Animales', 'fecha': '2026-08-01', 'tipo_animal': 'Bovino',
            'sexo': 'Macho', 'nombre': 'Toro', 'monto_total': '500000', 'costo_adquisicion': '500000',
        })
        self.assertEqual(response.status_code, 201)
        compra = Compra.objects.get(pk=response.json()['id'])
        animal = Animal.objects.get(compra=compra)

        Preniez.objects.create(
            madre=animal, fecha=date(2026, 7, 1), tipo='Natural', estado_actual='Preñada',
        )

        response = self.client.post(reverse('actualizar_compra', args=[compra.id]), {
            'tipo': 'Otros', 'fecha': '2026-08-01', 'monto_total': '500',
        })
        self.assertEqual(response.status_code, 200)
        animal.refresh_from_db()
        self.assertIsNone(animal.compra_id)
        self.assertTrue(Preniez.objects.filter(madre=animal).exists())

    def test_cambiar_tipo_compra_insumo_consumido_conserva_lote(self):
        response = self.client.post(reverse('crear_compra'), {
            'tipo': 'Insumos', 'fecha': '2026-08-01', 'nuevo_insumo': 'Vacuna aftosa',
            'tipo_insumo': 'Vacuna', 'cantidad': '50', 'precio_unitario': '100',
        })
        self.assertEqual(response.status_code, 201)
        compra = Compra.objects.get(pk=response.json()['id'])
        lote = compra.detalles.first().lote

        evento = EventoSanitario.objects.create(
            tipo='Vacunación', fecha_aplicacion=date(2026, 8, 2), estado=True,
            costo_total=Decimal('1000'), lote=lote, cantidad=Decimal('10'),
        )
        self.assertTrue(Consumo.objects.filter(lote=lote, evento_sanitario=evento).exists())

        response = self.client.post(reverse('actualizar_compra', args=[compra.id]), {
            'tipo': 'Otros', 'fecha': '2026-08-01', 'monto_total': '500',
        })
        self.assertEqual(response.status_code, 200)
        compra.refresh_from_db()
        self.assertEqual(compra.detalles.count(), 0)
        self.assertTrue(Lote.objects.filter(pk=lote.pk).exists())
        self.assertTrue(Consumo.objects.filter(lote=lote, evento_sanitario=evento).exists())


class MultiEstablecimientoTests(TestCase):
    def setUp(self):
        self.establecimiento_a = Establecimiento.objects.create(
            nombre='Establecimiento A', fecha_inicio=date.today(), ubicacion='Córdoba'
        )
        self.establecimiento_b = Establecimiento.objects.create(
            nombre='Establecimiento B', fecha_inicio=date.today(), ubicacion='Santa Fe'
        )
        persona = Persona.objects.create(
            nombre='Juan', apellido='Fernandez', correo_electronico='juan-multi@test.com',
        )
        self.usuario = Usuario.objects.create(
            nombre_usuario='propietario', clave=make_password('clave123'), persona=persona,
        )
        for establecimiento in (self.establecimiento_a, self.establecimiento_b):
            RolEstablecimiento.objects.create(
                usuario=self.usuario, establecimiento=establecimiento,
                nombre='Propietario', fecha_ingreso=date.today(), estado_acceso=True,
            )
        session = self.client.session
        session['usuario_id'] = self.usuario.id
        session['establecimiento_id'] = self.establecimiento_a.id
        session.save()

    def activar_establecimiento(self, establecimiento_id):
        session = self.client.session
        session['establecimiento_id'] = establecimiento_id
        session.save()

    def test_movimientos_financieros_creados_con_establecimiento(self):
        response = self.client.post(reverse('api_finanzas_movimientos'), {
            'fecha': '2026-08-01', 'tipo': 'Ingreso', 'nombre': 'Movimiento de A',
            'monto_total': '1000', 'detalle': '',
        })
        self.assertEqual(response.status_code, 201)
        movimiento_a = MovimientoFinanciero.objects.get(pk=response.json()['movimiento']['id'])
        self.assertEqual(movimiento_a.establecimiento, self.establecimiento_a)

        self.activar_establecimiento(self.establecimiento_b.id)
        response = self.client.post(reverse('api_finanzas_movimientos'), {
            'fecha': '2026-08-02', 'tipo': 'Egreso', 'nombre': 'Movimiento de B',
            'monto_total': '500', 'detalle': '',
        })
        self.assertEqual(response.status_code, 201)
        movimiento_b = MovimientoFinanciero.objects.get(pk=response.json()['movimiento']['id'])
        self.assertEqual(movimiento_b.establecimiento, self.establecimiento_b)

    def test_pagina_finanzas_muestra_solo_el_establecimiento_activo(self):
        MovimientoFinanciero.objects.create(
            fecha=date(2026, 8, 1), tipo='Ingreso', nombre='Concepto A',
            monto_total=Decimal('1000'), establecimiento=self.establecimiento_a,
        )
        MovimientoFinanciero.objects.create(
            fecha=date(2026, 8, 2), tipo='Egreso', nombre='Concepto B',
            monto_total=Decimal('500'), establecimiento=self.establecimiento_b,
        )

        response = self.client.get(reverse('finanzas'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Concepto A')
        self.assertNotContains(response, 'Concepto B')

        self.activar_establecimiento(self.establecimiento_b.id)
        response = self.client.get(reverse('finanzas'))
        self.assertContains(response, 'Concepto B')
        self.assertNotContains(response, 'Concepto A')

    def test_compra_asigna_establecimiento_a_lote_y_movimiento(self):
        response = self.client.post(reverse('crear_compra'), {
            'tipo': 'Insumos', 'fecha': '2026-08-01',
            'nuevo_insumo': 'Vacuna A', 'tipo_insumo': 'Vacuna',
            'cantidad': '10', 'precio_unitario': '100',
        })
        self.assertEqual(response.status_code, 201)
        compra = Compra.objects.get(pk=response.json()['id'])
        lote = compra.detalles.first().lote
        self.assertEqual(lote.establecimiento, self.establecimiento_a)
        self.assertEqual(compra.mov_financiero.establecimiento, self.establecimiento_a)

    def test_pagina_compras_muestra_solo_el_establecimiento_activo(self):
        self.client.post(reverse('crear_compra'), {
            'tipo': 'Maquinaria', 'fecha': '2026-08-01', 'detalle': 'Tractor de A',
            'monto_total': '300000',
        })
        self.activar_establecimiento(self.establecimiento_b.id)
        self.client.post(reverse('crear_compra'), {
            'tipo': 'Maquinaria', 'fecha': '2026-08-02', 'detalle': 'Tractor de B',
            'monto_total': '400000',
        })

        self.activar_establecimiento(self.establecimiento_a.id)
        response = self.client.get(reverse('compras'))
        self.assertContains(response, 'Tractor de A')
        self.assertNotContains(response, 'Tractor de B')

        self.activar_establecimiento(self.establecimiento_b.id)
        response = self.client.get(reverse('compras'))
        self.assertContains(response, 'Tractor de B')
        self.assertNotContains(response, 'Tractor de A')

    def test_venta_asigna_establecimiento_al_movimiento_y_se_muestra_separada(self):
        animal_a = Animal.objects.create(
            id_senasa=60001, nombre='Vaca de A', tipo_animal='Bovino', sexo='Hembra',
            vivo=True, peso_actual=Decimal('300'), establecimiento=self.establecimiento_a,
        )
        response = self.client.post(reverse('crear_venta'), {
            'fecha': '2026-08-01', 'precio_por_kg': '100', 'animales': [str(animal_a.idAnimal)],
            'peso_total': '300', 'peso_manual': 'on',
        })
        self.assertEqual(response.status_code, 201)
        venta = Venta.objects.get(pk=response.json()['id'])
        self.assertEqual(venta.mov_financiero.establecimiento, self.establecimiento_a)

        response = self.client.get(reverse('ventas'))
        self.assertContains(response, 'Vaca de A')

        self.activar_establecimiento(self.establecimiento_b.id)
        response = self.client.get(reverse('ventas'))
        self.assertNotContains(response, 'Vaca de A')

    def test_evento_sanitario_genera_movimiento_del_establecimiento(self):
        animal = Animal.objects.create(
            id_senasa=60002, nombre='Vaca evento A', tipo_animal='Bovino', sexo='Hembra',
            vivo=True, establecimiento=self.establecimiento_a,
        )
        response = self.client.post(reverse('crear_evento_sanitario'), {
            'tipo': 'Desparasitación', 'fecha_aplicacion': '2026-08-01', 'estado': 'on',
            'costo_total': '2000', 'animal_id': str(animal.idAnimal),
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertEqual(evento.mov_financiero.establecimiento, self.establecimiento_a)

    def test_lotes_de_sanidad_separados_por_establecimiento(self):
        self.client.post(reverse('crear_compra'), {
            'tipo': 'Insumos', 'fecha': '2026-08-01',
            'nuevo_insumo': 'Vacuna A', 'tipo_insumo': 'Vacuna',
            'lote_nombre': 'Lote A', 'cantidad': '10', 'precio_unitario': '100',
        })
        self.activar_establecimiento(self.establecimiento_b.id)
        self.client.post(reverse('crear_compra'), {
            'tipo': 'Insumos', 'fecha': '2026-08-02',
            'nuevo_insumo': 'Vacuna B', 'tipo_insumo': 'Vacuna',
            'lote_nombre': 'Lote B', 'cantidad': '20', 'precio_unitario': '50',
        })

        self.activar_establecimiento(self.establecimiento_a.id)
        response = self.client.get(reverse('sanidad'))
        self.assertContains(response, 'Lote A')
        self.assertNotContains(response, 'Lote B')

        self.activar_establecimiento(self.establecimiento_b.id)
        response = self.client.get(reverse('sanidad'))
        self.assertContains(response, 'Lote B')
        self.assertNotContains(response, 'Lote A')

    def test_pagina_insumos_muestra_stock_del_establecimiento_activo(self):
        insumo = Insumo.objects.create(nombre='Vacuna unica', tipo='Vacuna', unidadDeMedida='dosis')
        Lote.objects.create(
            insumo=insumo, nombre='Stock A', stockActual=Decimal('50'),
            establecimiento=self.establecimiento_a,
        )
        Lote.objects.create(
            insumo=insumo, nombre='Stock B', stockActual=Decimal('80'),
            establecimiento=self.establecimiento_b,
        )

        response = self.client.get(reverse('insumos'))
        self.assertContains(response, '50.00')
        self.assertNotContains(response, '80.00')

        self.activar_establecimiento(self.establecimiento_b.id)
        response = self.client.get(reverse('insumos'))
        self.assertContains(response, '80.00')
        self.assertNotContains(response, '50.00')

    def test_pagina_stock_incluye_establecimientos_y_parcelas_con_establecimiento(self):
        parcela_b = Parcela.objects.create(ancho=12, largo=30, establecimiento=self.establecimiento_b)
        response = self.client.get(reverse('stock'))
        self.assertEqual(response.status_code, 200)
        data = response.context['page_data']
        self.assertEqual(
            [e['id'] for e in data['establecimientos']],
            [self.establecimiento_a.id, self.establecimiento_b.id],
        )
        self.assertEqual(data['establecimiento_id'], self.establecimiento_a.id)
        self.assertTrue(any(
            p['id'] == parcela_b.id and p['establecimiento_id'] == self.establecimiento_b.id
            for p in data['parcelas']
        ))

    def test_crear_animal_asigna_establecimiento_activo_por_defecto(self):
        parcela = Parcela.objects.create(ancho=12, largo=30, establecimiento=self.establecimiento_a)
        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': '61001', 'nombre': 'Vaca nueva A', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'parcela_id': parcela.id,
        })
        self.assertEqual(response.status_code, 201)
        animal = Animal.objects.get(id_senasa=61001)
        self.assertEqual(animal.establecimiento, self.establecimiento_a)
        self.assertEqual(animal.parcela, parcela)

    def test_crear_animal_en_establecimiento_explicito(self):
        parcela = Parcela.objects.create(ancho=12, largo=30, establecimiento=self.establecimiento_b)
        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': '61002', 'nombre': 'Vaca nueva B', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'establecimiento_id': self.establecimiento_b.id,
            'parcela_id': parcela.id,
        })
        self.assertEqual(response.status_code, 201)
        animal = Animal.objects.get(id_senasa=61002)
        self.assertEqual(animal.establecimiento, self.establecimiento_b)

        response = self.client.get(reverse('stock_api'))
        self.assertNotIn(animal.idAnimal, [a['id'] for a in response.json()['animales']])

        self.activar_establecimiento(self.establecimiento_b.id)
        response = self.client.get(reverse('stock_api'))
        self.assertIn(animal.idAnimal, [a['id'] for a in response.json()['animales']])

    def test_actualizar_animal_cambia_de_establecimiento(self):
        parcela_b = Parcela.objects.create(ancho=12, largo=30, establecimiento=self.establecimiento_b)
        animal = Animal.objects.create(
            id_senasa=61003, nombre='Vaca mover', tipo_animal='Bovino', sexo='Hembra',
            vivo=True, establecimiento=self.establecimiento_a,
        )
        response = self.client.post(reverse('actualizar_animal', args=[animal.idAnimal]), {
            'id_senasa': '61003', 'nombre': 'Vaca mover', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'establecimiento_id': self.establecimiento_b.id,
            'parcela_id': parcela_b.id,
        })
        self.assertEqual(response.status_code, 200)
        animal.refresh_from_db()
        self.assertEqual(animal.establecimiento, self.establecimiento_b)
        self.assertEqual(animal.parcela, parcela_b)

    def test_parcela_de_otro_establecimiento_se_rechaza(self):
        parcela_b = Parcela.objects.create(ancho=12, largo=30, establecimiento=self.establecimiento_b)
        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': '61004', 'nombre': 'Vaca error', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'establecimiento_id': self.establecimiento_a.id,
            'parcela_id': parcela_b.id,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Animal.objects.filter(id_senasa=61004).exists())

    def test_operario_no_puede_asignar_animal_a_establecimiento_ajeno(self):
        parcela_b = Parcela.objects.create(ancho=12, largo=30, establecimiento=self.establecimiento_b)
        persona = Persona.objects.create(nombre='Peon', apellido='Limitado')
        operario = Usuario.objects.create(
            nombre_usuario='peon-limitado', clave=make_password('clave123'), persona=persona,
        )
        RolEstablecimiento.objects.create(
            usuario=operario, establecimiento=self.establecimiento_a,
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        session = self.client.session
        session['usuario_id'] = operario.id
        session['establecimiento_id'] = self.establecimiento_a.id
        session.save()

        response = self.client.post(reverse('crear_animal'), {
            'id_senasa': '61005', 'nombre': 'Vaca ajeno', 'sexo': 'Hembra',
            'tipo_animal': 'Bovino', 'establecimiento_id': self.establecimiento_b.id,
            'parcela_id': parcela_b.id,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Animal.objects.filter(id_senasa=61005).exists())

    def test_sin_establecimiento_en_sesion_se_selecciona_el_primero(self):
        session = self.client.session
        session['establecimiento_id'] = None
        session.save()
        response = self.client.get(reverse('stock'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.session.get('establecimiento_id'), self.establecimiento_a.id,
        )
        self.assertEqual(response.context['page_data']['establecimiento_id'], self.establecimiento_a.id)

    def test_seleccionar_establecimiento_rechaza_todos(self):
        for valor in ('', 'todos', 'all'):
            response = self.client.post(reverse('seleccionar_establecimiento'), {'establecimiento_id': valor})
            self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.session.get('establecimiento_id'), self.establecimiento_a.id,
        )

    def test_login_selecciona_el_primer_establecimiento(self):
        persona = Persona.objects.create(nombre='Nuevo', apellido='Propietario')
        Usuario.objects.create(
            nombre_usuario='multi-nuevo', clave=make_password('clave123'), persona=persona,
        )
        for establecimiento in (self.establecimiento_a, self.establecimiento_b):
            RolEstablecimiento.objects.create(
                usuario=Usuario.objects.get(nombre_usuario='multi-nuevo'), establecimiento=establecimiento,
                nombre='Propietario', fecha_ingreso=date.today(), estado_acceso=True,
            )
        response = self.client.post(reverse('login'), {'nombre_usuario': 'multi-nuevo', 'clave': 'clave123'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.client.session.get('establecimiento_id'), self.establecimiento_a.id,
        )


class SueldosModuleTests(TestCase):
    def setUp(self):
        self.establecimiento = Establecimiento.objects.create(
            nombre='Campo de prueba', fecha_inicio=date.today(), ubicacion='Córdoba'
        )
        persona = Persona.objects.create(
            nombre='Juan', apellido='Fernandez', correo_electronico='juan@test.com',
        )
        self.propietario = Usuario.objects.create(
            nombre_usuario='propietario', clave=make_password('clave123'), persona=persona,
        )
        RolEstablecimiento.objects.create(
            usuario=self.propietario, establecimiento=self.establecimiento,
            nombre='Propietario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        persona_empleado = Persona.objects.create(
            nombre='Pedro', apellido='Perez', correo_electronico='pedro@test.com',
        )
        self.empleado = Usuario.objects.create(
            nombre_usuario='pedro', clave=make_password('clave123'), persona=persona_empleado,
        )
        RolEstablecimiento.objects.create(
            usuario=self.empleado, establecimiento=self.establecimiento,
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        persona_otro = Persona.objects.create(
            nombre='Luis', apellido='Lopez', correo_electronico='luis@otro.com',
        )
        self.otro_establecimiento = Establecimiento.objects.create(
            nombre='Campo ajeno', fecha_inicio=date.today(), ubicacion='San Luis'
        )
        self.empleado_ajeno = Usuario.objects.create(
            nombre_usuario='luis', clave=make_password('clave123'), persona=persona_otro,
        )
        RolEstablecimiento.objects.create(
            usuario=self.empleado_ajeno, establecimiento=self.otro_establecimiento,
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        session = self.client.session
        session['usuario_id'] = self.propietario.id
        session['establecimiento_id'] = self.establecimiento.id
        session.save()

    def crear_liquidacion(self, datos):
        return self.client.post(reverse('crear_liquidacion'), datos)

    def test_pagina_sueldos_responde(self):
        response = self.client.get(reverse('sueldos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'window.HUACAPP_DATA')
        self.assertContains(response, 'Pedro')

    def test_pagina_gastos_incluye_sueldos_en_graficos(self):
        self.crear_liquidacion({
            'fecha': '2026-08-01', 'empleado_id': self.empleado.id, 'sueldo': '150000.50',
        })
        self.client.post(reverse('crear_compra'), {
            'tipo': 'Otros', 'fecha': '2026-08-01', 'monto_total': '300000', 'detalle': 'Tractor',
        })
        response = self.client.get(reverse('gastos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'window.HUACAPP_DATA')
        contenido = response.content.decode()
        inicio = contenido.index('id="huacapp-page-data"')
        inicio = contenido.index('>', inicio) + 1
        fin = contenido.index('</script>', inicio)
        datos = json.loads(contenido[inicio:fin])
        compras = json.loads(datos['chart_gastos']['compras_json'])
        sueldos = json.loads(datos['chart_gastos']['sueldos_json'])
        self.assertIn(float(Decimal('300000.00')), compras)
        self.assertIn(float(Decimal('150000.50')), sueldos)
        self.assertEqual(datos['summary']['total_gastos'], 2)
        self.assertAlmostEqual(datos['summary']['egresos_total'], 450000.50, places=2)
        self.assertEqual(datos['summary']['total_liquidaciones'], 1)

    def test_crear_liquidacion_crea_egreso_financiero(self):
        response = self.crear_liquidacion({
            'fecha': '2026-08-01', 'empleado_id': self.empleado.id, 'sueldo': '150000.50',
            'descripcion': 'Sueldo de agosto',
        })
        self.assertEqual(response.status_code, 201)
        liquidacion = LiquidacionSueldo.objects.get(pk=response.json()['id'])
        self.assertEqual(liquidacion.empleado, self.empleado)
        self.assertEqual(liquidacion.sueldo, Decimal('150000.50'))
        self.assertEqual(liquidacion.establecimiento, self.establecimiento)
        movimiento = liquidacion.movimiento_financiero
        self.assertIsNotNone(movimiento)
        self.assertEqual(movimiento.tipo, 'Egreso')
        self.assertEqual(movimiento.monto_total, Decimal('150000.50'))
        self.assertEqual(movimiento.nombre, 'Sueldo - Pedro Perez')
        self.assertEqual(response.json()['liquidacion']['empleado'], 'Pedro Perez')

    def test_sueldo_invalido_o_sin_empleado(self):
        response = self.crear_liquidacion({
            'fecha': '2026-08-01', 'empleado_id': self.empleado.id, 'sueldo': '0',
        })
        self.assertEqual(response.status_code, 400)
        response = self.crear_liquidacion({
            'fecha': '2026-08-01', 'empleado_id': '', 'sueldo': '10000',
        })
        self.assertEqual(response.status_code, 400)

    def test_empleado_de_otro_establecimiento(self):
        response = self.crear_liquidacion({
            'fecha': '2026-08-01', 'empleado_id': self.empleado_ajeno.id, 'sueldo': '10000',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('pertenece', response.json()['error'])

    def test_actualizar_liquidacion_actualiza_egreso(self):
        response = self.crear_liquidacion({
            'fecha': '2026-08-01', 'empleado_id': self.empleado.id, 'sueldo': '10000',
        })
        liquidacion_id = response.json()['id']
        response = self.client.post(reverse('actualizar_liquidacion', args=[liquidacion_id]), {
            'fecha': '2026-08-15', 'empleado_id': self.empleado.id, 'sueldo': '20000',
            'descripcion': 'Ajustado',
        })
        self.assertEqual(response.status_code, 200)
        liquidacion = LiquidacionSueldo.objects.get(pk=liquidacion_id)
        self.assertEqual(liquidacion.sueldo, Decimal('20000'))
        self.assertEqual(liquidacion.movimiento_financiero.monto_total, Decimal('20000'))
        self.assertEqual(liquidacion.movimiento_financiero.detalle, 'Ajustado')

    def test_eliminar_liquidacion_elimina_egreso(self):
        response = self.crear_liquidacion({
            'fecha': '2026-08-01', 'empleado_id': self.empleado.id, 'sueldo': '10000',
        })
        liquidacion_id = response.json()['id']
        movimiento_id = LiquidacionSueldo.objects.get(pk=liquidacion_id).movimiento_financiero_id
        response = self.client.post(reverse('eliminar_liquidacion', args=[liquidacion_id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LiquidacionSueldo.objects.filter(pk=liquidacion_id).exists())
        self.assertFalse(MovimientoFinanciero.objects.filter(pk=movimiento_id, activo=True).exists())


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
        self._loguear('preniez-tester')

    def _loguear(self, nombre_usuario):
        persona = Persona.objects.create(nombre=nombre_usuario, apellido='Test')
        usuario = Usuario.objects.create(
            nombre_usuario=nombre_usuario, clave=make_password('clave123'), persona=persona,
        )
        session = self.client.session
        session['usuario_id'] = usuario.id
        session.save()

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
        self.assertEqual(cria.id_senasa, '50000')
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
        self.establecimiento = Establecimiento.objects.create(
            nombre='Campo de prueba', fecha_inicio=date.today(), ubicacion='Córdoba',
        )
        persona = Persona.objects.create(nombre='Propietario', apellido='Test')
        usuario = Usuario.objects.create(
            nombre_usuario='propietario', clave=make_password('clave123'), persona=persona,
        )
        RolEstablecimiento.objects.create(
            usuario=usuario, establecimiento=self.establecimiento, nombre='Propietario',
            fecha_ingreso=date.today(), estado_acceso=True,
        )
        session = self.client.session
        session['usuario_id'] = usuario.id
        session.save()

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

    def test_inseminacion_sin_padre_es_opcional(self):
        response = self.client.post(reverse('crear_evento_inseminacion'), {
            'fecha_aplicacion': '2026-08-06', 'estado': 'true', 'tipo_animal': 'Bovino',
            'animales': [self.vaca1.idAnimal],
        })
        self.assertEqual(response.status_code, 201)
        evento = EventoSanitario.objects.get(pk=response.json()['evento']['id'])
        self.assertIsNone(evento.padre_id)
        self.assertEqual(response.json()['evento']['padre'], '-')

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
        self.assertEqual(cria.id_senasa, '99999')
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
    def test_propietario_crea_usuario_con_varios_establecimientos(self):
        segundo = Establecimiento.objects.create(
            nombre='Campo Sur', fecha_inicio=date.today(), ubicacion='Santa Fe',
        )
        # Un propietario accede automáticamente a todos los establecimientos.
        response = self.client.post(reverse('crear_usuario_api'), {
            'nombre': 'María', 'usuario': 'maria', 'clave': 'clave123',
            'rol': 'Propietario',
        })
        self.assertEqual(response.status_code, 201)
        usuario = Usuario.objects.get(nombre_usuario='maria')
        roles = RolEstablecimiento.objects.filter(usuario=usuario).order_by('establecimiento__id')
        self.assertEqual(len(roles), 2)
        self.assertEqual(list(roles.values_list('nombre', flat=True)), ['Propietario', 'Propietario'])
        self.assertEqual(list(roles.values_list('establecimiento_id', flat=True)),
                         [Establecimiento.objects.first().id, segundo.id])
        self.assertTrue(usuario.debe_cambiar_clave)

    def test_configuracion_solo_establecimiento(self):
        response = self.client.get(reverse('configuracion'))
        self.assertContains(response, 'tab-establecimiento')
        self.assertContains(response, 'est-logo-input')
        for seccion in ('tab-empresa', 'tab-categorias', 'tab-razas', 'tab-vacunas',
                        'tab-parcelas', 'tab-usuarios-roles', 'tabla-categorias',
                        'tabla-vacunas', 'tabla-estados-parcela', 'modalListaSimple'):
            self.assertNotContains(response, seccion)

    def test_config_establecimiento_guarda_datos_y_logo(self):
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        logo = SimpleUploadedFile('logo.png', png, content_type='image/png')
        response = self.client.post(reverse('config_establecimiento_api'), {
            'nombre': 'Campo Norte',
            'fecha_inicio': '2015-03-10',
            'ubicacion': 'Chaco',
            'logo': logo,
        })
        self.assertEqual(response.status_code, 200)
        establecimiento = Establecimiento.objects.get()
        self.assertEqual(establecimiento.nombre, 'Campo Norte')
        self.assertEqual(establecimiento.ubicacion, 'Chaco')
        self.assertEqual(establecimiento.fecha_inicio.isoformat(), '2015-03-10')
        self.assertTrue(establecimiento.logo)

        response = self.client.post(reverse('config_establecimiento_api'), {
            'nombre': '', 'ubicacion': 'Chaco',
        })
        self.assertEqual(response.status_code, 400)

        response = self.client.post(reverse('config_establecimiento_api'), {
            'nombre': 'Campo', 'fecha_inicio': 'no-es-fecha', 'ubicacion': 'Chaco',
        })
        self.assertEqual(response.status_code, 400)

    def test_eliminar_logo_establecimiento(self):
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        logo = SimpleUploadedFile('logo.png', png, content_type='image/png')
        establecimiento = Establecimiento.objects.get()
        establecimiento.logo = logo
        establecimiento.save()
        self.assertTrue(establecimiento.logo)

        response = self.client.post(reverse('eliminar_logo_establecimiento'))
        self.assertEqual(response.status_code, 200)
        establecimiento.refresh_from_db()
        self.assertFalse(establecimiento.logo)

        response = self.client.post(reverse('eliminar_logo_establecimiento'))
        self.assertEqual(response.status_code, 200)

    def test_eliminar_establecimiento_oculta_y_conserva_dependencias(self):
        segundo = Establecimiento.objects.create(
            nombre='Campo Chico', fecha_inicio=date.today(), ubicacion='Salta'
        )
        parcela_segunda = Parcela.objects.create(ancho=15, largo=20, establecimiento=segundo)
        animal = Animal.objects.create(
            id_senasa=999, nombre='Toro', tipo_animal='Bovino', sexo='Macho',
            establecimiento=segundo, parcela=parcela_segunda, vivo=True,
        )
        rol = RolEstablecimiento.objects.create(
            usuario=Usuario.objects.get(nombre_usuario='propietario'),
            establecimiento=segundo, nombre='Propietario',
            fecha_ingreso=date.today(), estado_acceso=True,
        )

        self.client.post(reverse('seleccionar_establecimiento'), {'establecimiento_id': segundo.id})
        response = self.client.post(reverse('eliminar_establecimiento', args=[segundo.id]))
        self.assertEqual(response.status_code, 200)

        self.assertFalse(Establecimiento.objects.filter(pk=segundo.id, activo=True).exists())
        self.assertTrue(Parcela.objects.filter(pk=parcela_segunda.id).exists())
        self.assertTrue(RolEstablecimiento.objects.filter(pk=rol.id).exists())
        animal.refresh_from_db()
        self.assertEqual(animal.establecimiento, segundo)
        self.assertEqual(animal.parcela, parcela_segunda)
        self.assertNotIn('establecimiento_id', self.client.session)

    def test_no_se_elimina_el_unico_establecimiento(self):
        response = self.client.post(reverse('eliminar_establecimiento', args=[Establecimiento.objects.get().id]))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Establecimiento.objects.exists())

    def test_eliminar_establecimiento_inexistente(self):
        response = self.client.post(reverse('eliminar_establecimiento', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_operario_no_elimina_establecimientos(self):
        persona = Persona.objects.create(nombre='Pedro', correo_electronico='pedro-elim@auth.com')
        operario = Usuario.objects.create(nombre_usuario='pedro-elim', clave=make_password('clave123'), persona=persona)
        RolEstablecimiento.objects.create(
            usuario=operario, establecimiento=Establecimiento.objects.get(),
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        session = self.client.session
        session['usuario_id'] = operario.id
        session.save()
        response = self.client.post(reverse('eliminar_establecimiento', args=[Establecimiento.objects.get().id]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Establecimiento.objects.exists())


class AuthTests(TestCase):
    def setUp(self):
        Establecimiento.objects.create(
            nombre='Campo de prueba', fecha_inicio=date.today(), ubicacion='Córdoba'
        )

    def login_usuario(self, usuario):
        session = self.client.session
        session['usuario_id'] = usuario.id
        session.save()

    def test_paginas_requieren_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

        response = self.client.get(reverse('stock_api'))
        self.assertEqual(response.status_code, 401)

    def test_no_hay_registro_publico(self):
        response = self.client.get('/registro/')
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Registrate')
        self.assertNotContains(response, 'Creá tu cuenta')

    def test_login_y_logout(self):
        persona = Persona.objects.create(nombre='Juan', correo_electronico='juan@auth2.com')
        Usuario.objects.create(nombre_usuario='juan', clave=make_password('clave123'), persona=persona)

        response = self.client.post(reverse('login'), {'nombre_usuario': 'juan', 'clave': 'clave123'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
        self.assertIn('usuario_id', self.client.session)

        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('usuario_id', self.client.session)

    def test_login_con_clave_incorrecta(self):
        persona = Persona.objects.create(nombre='Juan', correo_electronico='juan@auth3.com')
        Usuario.objects.create(nombre_usuario='juan', clave=make_password('clave123'), persona=persona)
        response = self.client.post(reverse('login'), {'nombre_usuario': 'juan', 'clave': 'incorrecta'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuario o contraseña incorrectos')

    def test_login_con_clave_temporal_exige_cambio(self):
        persona = Persona.objects.create(nombre='Juan', correo_electronico='juan@temp.com')
        Usuario.objects.create(
            nombre_usuario='juan', clave=make_password('temporal123'),
            persona=persona, debe_cambiar_clave=True,
        )
        response = self.client.post(reverse('login'), {'nombre_usuario': 'juan', 'clave': 'temporal123'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('cambiar_clave'))

        # Mientras conserve la clave temporal no puede navegar el sistema.
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('cambiar_clave'))

        # Cambio de clave: entra al dashboard y la clave nueva funciona.
        response = self.client.post(reverse('cambiar_clave'), {
            'correo_electronico': 'juan@temp.com',
            'clave': 'nueva123',
            'clave_confirmacion': 'nueva123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
        self.client.session.flush()
        response = self.client.post(reverse('login'), {'nombre_usuario': 'juan', 'clave': 'nueva123'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_cambiar_clave_exige_correo(self):
        persona = Persona.objects.create(nombre='Juan', correo_electronico='juan@temp3.com')
        Usuario.objects.create(
            nombre_usuario='juan', clave=make_password('temporal123'),
            persona=persona, debe_cambiar_clave=True,
        )
        self.client.post(reverse('login'), {'nombre_usuario': 'juan', 'clave': 'temporal123'})

        # Sin correo no permite cambiar la clave.
        response = self.client.post(reverse('cambiar_clave'), {
            'clave': 'nueva123', 'clave_confirmacion': 'nueva123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'correo electrónico')
        usuario = Usuario.objects.get(nombre_usuario='juan')
        self.assertTrue(usuario.debe_cambiar_clave)

        # Con un correo que no coincide con el registrado, tampoco.
        response = self.client.post(reverse('cambiar_clave'), {
            'correo_electronico': 'otro@mail.com',
            'clave': 'nueva123', 'clave_confirmacion': 'nueva123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no coincide')

        # Con el correo correcto, cambia la clave y la guarda.
        response = self.client.post(reverse('cambiar_clave'), {
            'correo_electronico': 'juan@temp3.com',
            'clave': 'nueva123', 'clave_confirmacion': 'nueva123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
        usuario.refresh_from_db()
        self.assertFalse(usuario.debe_cambiar_clave)

    def test_propietario_edita_datos_personales_de_usuario(self):
        persona_prop = Persona.objects.create(nombre='Dueño', correo_electronico='dueno@editar.com')
        propietario = Usuario.objects.create(
            nombre_usuario='dueno', clave=make_password('clave123'), persona=persona_prop,
        )
        RolEstablecimiento.objects.create(
            usuario=propietario, establecimiento=Establecimiento.objects.get(),
            nombre='Propietario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        self.login_usuario(propietario)

        persona = Persona.objects.create(nombre='Pedro', apellido='Gómez', correo_electronico='pedro@editar.com')
        usuario = Usuario.objects.create(
            nombre_usuario='pedro', clave=make_password('clave123'), persona=persona,
        )
        RolEstablecimiento.objects.create(
            usuario=usuario, establecimiento=Establecimiento.objects.get(),
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )

        response = self.client.post(reverse('actualizar_usuario_api', args=[usuario.id]), {
            'nombre': 'Pedro Pablo',
            'apellido': 'Gómez',
            'email': 'pedro.pablo@editar.com',
            'telefono': '3515551234',
        })
        self.assertEqual(response.status_code, 200)
        usuario.refresh_from_db()
        persona.refresh_from_db()
        self.assertEqual(persona.nombre, 'Pedro Pablo')
        self.assertEqual(persona.correo_electronico, 'pedro.pablo@editar.com')
        self.assertEqual(persona.telefono, '3515551234')

        # Un correo ya usado por otro usuario es rechazado.
        Persona.objects.create(nombre='Otra', correo_electronico='ocupado@editar.com')
        response = self.client.post(reverse('actualizar_usuario_api', args=[usuario.id]), {
            'nombre': 'Pedro Pablo', 'email': 'ocupado@editar.com',
        })
        self.assertEqual(response.status_code, 400)
        persona.refresh_from_db()
        self.assertEqual(persona.correo_electronico, 'pedro.pablo@editar.com')

    def test_login_no_reutiliza_la_clave_temporal(self):
        persona = Persona.objects.create(nombre='Juan', correo_electronico='juan@temp2.com')
        Usuario.objects.create(
            nombre_usuario='juan', clave=make_password('temporal123'),
            persona=persona, debe_cambiar_clave=True,
        )
        self.client.post(reverse('login'), {'nombre_usuario': 'juan', 'clave': 'temporal123'})
        response = self.client.post(reverse('cambiar_clave'), {
            'correo_electronico': 'juan@temp2.com',
            'clave': 'temporal123',
            'clave_confirmacion': 'temporal123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no puede ser igual a la anterior')
        usuario = Usuario.objects.get(nombre_usuario='juan')
        self.assertTrue(usuario.debe_cambiar_clave)

    def test_propietario_crea_operario_y_le_da_acceso(self):
        persona = Persona.objects.create(nombre='Juan', correo_electronico='juan-multi@auth.com')
        propietario = Usuario.objects.create(
            nombre_usuario='propietario', clave=make_password('clave123'), persona=persona,
        )
        est1 = Establecimiento.objects.get()
        est2 = Establecimiento.objects.create(
            nombre='Segundo campo', fecha_inicio=date.today(), ubicacion='Córdoba'
        )
        RolEstablecimiento.objects.create(
            usuario=propietario, establecimiento=est1,
            nombre='Propietario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        self.login_usuario(propietario)

        # Un operario accede solo a los establecimientos elegidos.
        response = self.client.post(reverse('crear_usuario_api'), {
            'nombre': 'Pedro', 'usuario': 'pedro', 'clave': 'clave123',
            'rol': 'Operario', 'establecimiento_ids': [est1.id, est2.id],
        })
        self.assertEqual(response.status_code, 201)
        usuario = Usuario.objects.get(nombre_usuario='pedro')
        self.assertEqual(
            list(RolEstablecimiento.objects.filter(usuario=usuario).values_list('establecimiento_id', flat=True)),
            [est1.id, est2.id],
        )

        # Si se vuelve propietario, obtiene acceso a todos los establecimientos.
        response = self.client.post(reverse('actualizar_usuario_api', args=[usuario.id]), {
            'rol': 'Propietario', 'estado_acceso': 'Activo',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(RolEstablecimiento.objects.filter(usuario=usuario, nombre='Propietario').values_list('establecimiento_id', flat=True)),
            {est1.id, est2.id},
        )

        # Un establecimiento nuevo se sincroniza automáticamente para el propietario.
        response = self.client.post(reverse('crear_establecimiento'), {
            'nombre': 'Tercer campo', 'fecha_inicio': '2026-08-01', 'ubicacion': 'Córdoba',
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            RolEstablecimiento.objects.filter(usuario=usuario, nombre='Propietario', establecimiento__nombre='Tercer campo').exists()
        )

        # Desactivar el acceso apaga todos los accesos del usuario.
        response = self.client.post(reverse('actualizar_usuario_api', args=[usuario.id]), {
            'estado_acceso': 'Inactivo',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(RolEstablecimiento.objects.filter(usuario=usuario, estado_acceso=True).exists())

    def test_operario_no_accede_a_finanzas_pero_si_a_stock(self):
        persona = Persona.objects.create(nombre='Pedro', correo_electronico='pedro@auth.com')
        usuario = Usuario.objects.create(nombre_usuario='pedro', clave=make_password('clave123'), persona=persona)
        establecimiento = Establecimiento.objects.get()
        RolEstablecimiento.objects.create(
            usuario=usuario, establecimiento=establecimiento,
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        self.login_usuario(usuario)

        self.assertEqual(self.client.get(reverse('stock')).status_code, 200)
        self.assertEqual(self.client.get(reverse('finanzas')).status_code, 302)
        self.assertEqual(self.client.get(reverse('usuarios')).status_code, 200)
        self.assertEqual(self.client.get(reverse('ventas')).status_code, 302)
        response = self.client.post(reverse('crear_venta'), {'precio_por_kg': '100', 'animales': []})
        self.assertEqual(response.status_code, 403)

    def test_operario_no_crea_establecimientos(self):
        persona = Persona.objects.create(nombre='Pedro', correo_electronico='pedro2@auth.com')
        usuario = Usuario.objects.create(nombre_usuario='pedro2', clave=make_password('clave123'), persona=persona)
        RolEstablecimiento.objects.create(
            usuario=usuario, establecimiento=Establecimiento.objects.get(),
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        self.login_usuario(usuario)
        response = self.client.post(reverse('crear_establecimiento'), {
            'nombre': 'Nuevo', 'fecha_inicio': '2026-08-01', 'ubicacion': 'X',
        })
        self.assertEqual(response.status_code, 403)

    def test_operario_ve_solo_su_propia_informacion_en_usuarios(self):
        persona = Persona.objects.create(nombre='Pedro', correo_electronico='pedro-self@auth.com')
        usuario = Usuario.objects.create(nombre_usuario='pedro', clave=make_password('clave123'), persona=persona)
        RolEstablecimiento.objects.create(
            usuario=usuario, establecimiento=Establecimiento.objects.get(),
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        otro = Persona.objects.create(nombre='Ana', correo_electronico='ana-self@auth.com')
        Usuario.objects.create(nombre_usuario='ana', clave=make_password('clave123'), persona=otro)
        self.login_usuario(usuario)

        response = self.client.get(reverse('usuarios'))
        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode()
        # El operario solo recibe su propia información en el listado.
        inicio = contenido.index('id="huacapp-data-usuarios"')
        inicio = contenido.index('>', inicio) + 1
        fin = contenido.index('</script>', inicio)
        usuarios = json.loads(contenido[inicio:fin])
        self.assertEqual([u['usuario'] for u in usuarios], ['pedro'])
        # No se le ofrece alta de usuarios ni el listado con filtros.
        self.assertNotContains(response, 'modalNuevoUsuario')
        self.assertNotContains(response, 'btn-limpiar-filtros')

    def test_operario_edita_sus_datos_pero_no_los_roles(self):
        persona = Persona.objects.create(nombre='Pedro', correo_electronico='pedro-self2@auth.com')
        usuario = Usuario.objects.create(nombre_usuario='pedro', clave=make_password('clave123'), persona=persona)
        rol = RolEstablecimiento.objects.create(
            usuario=usuario, establecimiento=Establecimiento.objects.get(),
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        otro = Persona.objects.create(nombre='Ana', correo_electronico='ana-self2@auth.com')
        usuario_otro = Usuario.objects.create(nombre_usuario='ana', clave=make_password('clave123'), persona=otro)
        self.login_usuario(usuario)

        # Puede editar sus propios datos personales y su clave (con la clave actual).
        response = self.client.post(reverse('actualizar_usuario_api', args=[usuario.id]), {
            'nombre': 'Pedro Pablo',
            'email': 'pedro.self2@auth.com',
            'telefono': '3515559999',
            'clave_actual': 'clave123',
            'clave': 'nuevaclave1',
            'rol': 'Propietario',
            'estado_acceso': 'Inactivo',
            'establecimiento_ids': ['999'],
        })
        self.assertEqual(response.status_code, 200)
        persona.refresh_from_db()
        rol.refresh_from_db()
        self.assertEqual(persona.nombre, 'Pedro Pablo')
        self.assertEqual(persona.telefono, '3515559999')
        self.assertTrue(rol.estado_acceso)
        self.assertEqual(rol.nombre, 'Operario')
        usuario.refresh_from_db()
        self.assertTrue(usuario.clave.startswith('pbkdf2'))
        self.assertFalse(usuario.debe_cambiar_clave)

        # Sin la clave actual no puede cambiar su propia contraseña.
        response = self.client.post(reverse('actualizar_usuario_api', args=[usuario.id]), {
            'clave': 'otraclave1',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('contraseña actual', response.json()['error'].lower())
        # Con una clave actual incorrecta tampoco.
        response = self.client.post(reverse('actualizar_usuario_api', args=[usuario.id]), {
            'clave_actual': 'incorrecta',
            'clave': 'otraclave1',
        })
        self.assertEqual(response.status_code, 400)
        # La nueva contraseña no puede ser igual a la actual.
        response = self.client.post(reverse('actualizar_usuario_api', args=[usuario.id]), {
            'clave_actual': 'nuevaclave1',
            'clave': 'nuevaclave1',
        })
        self.assertEqual(response.status_code, 400)

        # No puede editar los datos de otro usuario.
        response = self.client.post(reverse('actualizar_usuario_api', args=[usuario_otro.id]), {
            'nombre': 'Ana María',
        })
        self.assertEqual(response.status_code, 403)
        usuario_otro.persona.refresh_from_db()
        self.assertEqual(usuario_otro.persona.nombre, 'Ana')

    def test_operario_no_crea_ni_elimina_usuarios(self):
        persona = Persona.objects.create(nombre='Pedro', correo_electronico='pedro-self3@auth.com')
        usuario = Usuario.objects.create(nombre_usuario='pedro', clave=make_password('clave123'), persona=persona)
        RolEstablecimiento.objects.create(
            usuario=usuario, establecimiento=Establecimiento.objects.get(),
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        self.login_usuario(usuario)
        response = self.client.post(reverse('crear_usuario_api'), {
            'nombre': 'Otro', 'usuario': 'otro', 'clave': 'clave123',
        })
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('eliminar_usuario_api', args=[usuario.id]))
        self.assertEqual(response.status_code, 403)

    def test_propietario_restablece_clave_de_otro_sin_clave_actual(self):
        persona_prop = Persona.objects.create(nombre='Dueño', correo_electronico='dueno-reset@auth.com')
        propietario = Usuario.objects.create(
            nombre_usuario='dueno', clave=make_password('clave123'), persona=persona_prop,
        )
        RolEstablecimiento.objects.create(
            usuario=propietario, establecimiento=Establecimiento.objects.get(),
            nombre='Propietario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        persona = Persona.objects.create(nombre='Pedro', correo_electronico='pedro-reset@auth.com')
        operario = Usuario.objects.create(
            nombre_usuario='pedro', clave=make_password('clave123'), persona=persona,
        )
        RolEstablecimiento.objects.create(
            usuario=operario, establecimiento=Establecimiento.objects.get(),
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        self.login_usuario(propietario)

        # El propietario restablece la clave de otro usuario sin conocer la actual,
        # y esa clave pasa a ser temporal (se debe cambiar en el próximo ingreso).
        response = self.client.post(reverse('actualizar_usuario_api', args=[operario.id]), {
            'clave': 'temporal123',
        })
        self.assertEqual(response.status_code, 200)
        operario.refresh_from_db()
        self.assertTrue(operario.clave.startswith('pbkdf2'))
        self.assertTrue(operario.debe_cambiar_clave)

        # El propietario que cambia su propia clave sí debe indicar la actual.
        response = self.client.post(reverse('actualizar_usuario_api', args=[propietario.id]), {
            'clave': 'miclavenueva1',
        })
        self.assertEqual(response.status_code, 400)

    def test_recuperar_contrasena_envia_correo(self):
        persona = Persona.objects.create(nombre='Juan', correo_electronico='juan@recuperar.com')
        Usuario.objects.create(nombre_usuario='juan', clave=make_password('clave123'), persona=persona)
        response = self.client.post(reverse('recuperar'), {'correo_electronico': 'juan@recuperar.com'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'enviamos un enlace')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/recuperar/', mail.outbox[0].body)

    def test_propietario_crea_usuario_y_asigna_rol(self):
        persona = Persona.objects.create(nombre='Juan', correo_electronico='juan-pro@auth.com')
        propietario = Usuario.objects.create(
            nombre_usuario='propietario', clave=make_password('clave123'), persona=persona,
        )
        RolEstablecimiento.objects.create(
            usuario=propietario, establecimiento=Establecimiento.objects.get(),
            nombre='Propietario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        self.login_usuario(propietario)

        response = self.client.post(reverse('crear_usuario_api'), {
            'nombre': 'Pedro', 'apellido': 'Gómez', 'email': 'pedro@creado.com',
            'usuario': 'pedro', 'clave': 'clave123', 'rol': 'Operario',
        })
        self.assertEqual(response.status_code, 201)
        usuario = Usuario.objects.get(nombre_usuario='pedro')
        rol = RolEstablecimiento.objects.get(usuario=usuario)
        self.assertEqual(rol.nombre, 'Operario')
        self.assertEqual(rol.establecimiento, Establecimiento.objects.get())

        response = self.client.post(reverse('actualizar_usuario_api', args=[usuario.id]), {
            'rol': 'Propietario', 'estado_acceso': 'Activo',
        })
        self.assertEqual(response.status_code, 200)
        rol.refresh_from_db()
        self.assertEqual(rol.nombre, 'Propietario')

        # Un operario no puede administrar usuarios.
        persona_operario = Persona.objects.create(nombre='Ana', correo_electronico='ana-pro@auth.com')
        operario = Usuario.objects.create(
            nombre_usuario='ana', clave=make_password('clave123'), persona=persona_operario,
        )
        RolEstablecimiento.objects.create(
            usuario=operario, establecimiento=Establecimiento.objects.get(),
            nombre='Operario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        self.login_usuario(operario)
        response = self.client.post(reverse('crear_usuario_api'), {
            'nombre': 'X', 'usuario': 'x', 'clave': 'clave123', 'rol': 'Operario',
        })
        self.assertEqual(response.status_code, 403)


class NotificacionesTests(TestCase):
    def setUp(self):
        self.establecimiento = Establecimiento.objects.create(
            nombre='Campo notif', fecha_inicio=date.today(), ubicacion='Chaco'
        )
        persona = Persona.objects.create(nombre='Nora', correo_electronico='nora-notif@test.com')
        self.usuario = Usuario.objects.create(
            nombre_usuario='nora-notif', clave=make_password('clave123'), persona=persona,
        )
        RolEstablecimiento.objects.create(
            usuario=self.usuario, establecimiento=self.establecimiento,
            nombre='Propietario', fecha_ingreso=date.today(), estado_acceso=True,
        )
        session = self.client.session
        session['usuario_id'] = self.usuario.id
        session.save()

    def _crear_vacuna_vencida(self):
        insumo = Insumo.objects.create(nombre='Vacuna aftosa', tipo='Vacuna', unidadDeMedida='dosis')
        return Lote.objects.create(
            insumo=insumo, nombre='Lote vencido', stockActual=Decimal('10'),
            fechaVencimiento=date(2020, 1, 1), establecimiento=self.establecimiento,
        )

    def test_api_crea_y_lista_notificaciones(self):
        self._crear_vacuna_vencida()
        respuesta = self.client.get(reverse('notificaciones_api'))
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['no_leidas'], 1)
        notificacion = datos['notificaciones'][0]
        self.assertEqual(notificacion['clave'], 'vacunas_vencidas')
        self.assertFalse(notificacion['leida'])
        self.assertEqual(notificacion['url'], reverse('insumos'))
        self.assertTrue(Notificacion.objects.filter(usuario=self.usuario).exists())

    def test_marcar_leida_baja_el_contador(self):
        self._crear_vacuna_vencida()
        self.client.get(reverse('notificaciones_api'))
        notificacion = Notificacion.objects.get(usuario=self.usuario, clave='vacunas_vencidas')
        respuesta = self.client.post(reverse('marcar_notificacion_leida', args=[notificacion.id]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['no_leidas'], 0)
        notificacion.refresh_from_db()
        self.assertTrue(notificacion.leida)

    def test_eliminar_notificacion_no_se_vuelve_a_crear(self):
        self._crear_vacuna_vencida()
        self.client.get(reverse('notificaciones_api'))
        notificacion = Notificacion.objects.get(usuario=self.usuario, clave='vacunas_vencidas')
        respuesta = self.client.post(reverse('eliminar_notificacion', args=[notificacion.id]))
        self.assertEqual(respuesta.status_code, 200)
        datos = self.client.get(reverse('notificaciones_api')).json()
        self.assertEqual(datos['notificaciones'], [])
        self.assertEqual(datos['no_leidas'], 0)
        notificacion.refresh_from_db()
        self.assertTrue(notificacion.eliminada)

    def test_marcar_todas_leidas_y_eliminar_todas(self):
        self._crear_vacuna_vencida()
        self.client.get(reverse('notificaciones_api'))
        respuesta = self.client.post(reverse('marcar_todas_notificaciones_leidas'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['no_leidas'], 0)
        respuesta = self.client.post(reverse('eliminar_todas_notificaciones'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['no_leidas'], 0)
        datos = self.client.get(reverse('notificaciones_api')).json()
        self.assertEqual(datos['notificaciones'], [])

    def test_no_puede_marcar_notificacion_de_otro_usuario(self):
        self._crear_vacuna_vencida()
        persona = Persona.objects.create(nombre='Otra', correo_electronico='otra-notif@test.com')
        usuario_otro = Usuario.objects.create(
            nombre_usuario='otra-notif', clave=make_password('clave123'), persona=persona,
        )
        notificacion_otro = Notificacion.objects.create(
            usuario=usuario_otro, establecimiento=self.establecimiento,
            clave='bajo_peso', titulo='X', detalle='', url='/stock/',
        )
        respuesta = self.client.post(reverse('marcar_notificacion_leida', args=[notificacion_otro.id]))
        self.assertEqual(respuesta.status_code, 404)

    def test_eventos_programados_generan_notificacion(self):
        parcela = Parcela.objects.create(ancho=10, largo=20, establecimiento=self.establecimiento)
        animal = Animal.objects.create(
            id_senasa=77777, nombre='Vaca', tipo_animal='Bovino', sexo='Hembra',
            parcela=parcela, establecimiento=self.establecimiento, vivo=True,
        )
        evento = EventoSanitario.objects.create(
            tipo='Vacunación', fecha_aplicacion=date(2099, 1, 1), estado=False,
        )
        DetalleEvento.objects.create(evento=evento, animal=animal)

        datos = self.client.get(reverse('notificaciones_api')).json()
        claves = [n['clave'] for n in datos['notificaciones']]
        self.assertIn('proximos_eventos', claves)
        notificacion = next(n for n in datos['notificaciones'] if n['clave'] == 'proximos_eventos')
        self.assertEqual(notificacion['url'], reverse('sanidad'))
        self.assertEqual(datos['no_leidas'], 1)

        # Al aplicar el evento, la notificación deja de aparecer.
        evento.estado = True
        evento.save()
        datos = self.client.get(reverse('notificaciones_api')).json()
        claves = [n['clave'] for n in datos['notificaciones']]
        self.assertNotIn('proximos_eventos', claves)

    def test_insumos_agotados_generan_notificacion(self):
        insumo_vacio = Insumo.objects.create(nombre='Antiparasitario', tipo='Medicamento', unidadDeMedida='dosis')
        Lote.objects.create(
            insumo=insumo_vacio, nombre='Lote vacío', stockActual=Decimal('0'),
            establecimiento=self.establecimiento,
        )
        insumo_con_stock = Insumo.objects.create(nombre='Vacuna aftosa', tipo='Vacuna', unidadDeMedida='dosis')
        Lote.objects.create(
            insumo=insumo_con_stock, nombre='Lote con stock', stockActual=Decimal('50'),
            establecimiento=self.establecimiento,
        )
        datos = self.client.get(reverse('notificaciones_api')).json()
        notificaciones = {n['clave']: n for n in datos['notificaciones']}
        self.assertIn('insumos_agotados', notificaciones)
        self.assertEqual(notificaciones['insumos_agotados']['url'], reverse('insumos'))
        self.assertIn('Antiparasitario', notificaciones['insumos_agotados']['detalle'])
        self.assertNotIn('Vacuna aftosa', notificaciones['insumos_agotados']['detalle'])

    def test_compras_pendientes_generan_notificacion(self):
        movimiento = MovimientoFinanciero.objects.create(
            tipo='Egreso', nombre='Compra de insumos', monto_total=Decimal('5000.00'),
            fecha=date.today(), establecimiento=self.establecimiento,
        )
        Compra.objects.create(
            tipo='Insumos', fecha=date.today(), monto_total=Decimal('5000.00'),
            estadoDePago='Pendiente', mov_financiero=movimiento,
        )
        datos = self.client.get(reverse('notificaciones_api')).json()
        notificaciones = {n['clave']: n for n in datos['notificaciones']}
        self.assertIn('compras_pendientes', notificaciones)
        self.assertEqual(notificaciones['compras_pendientes']['url'], reverse('gastos'))

    def test_ventas_pendientes_generan_notificacion(self):
        parcela = Parcela.objects.create(ancho=10, largo=20, establecimiento=self.establecimiento)
        animal = Animal.objects.create(
            id_senasa=66666, nombre='Vaca venta', tipo_animal='Bovino', sexo='Hembra',
            parcela=parcela, establecimiento=self.establecimiento, vivo=True,
        )
        venta = Venta.objects.create(
            tipo='Venta', fecha=date.today(), monto_total=Decimal('8000.00'),
            estadoDeCobro='Pendiente',
        )
        animal.venta = venta
        animal.save(update_fields=['venta'])
        datos = self.client.get(reverse('notificaciones_api')).json()
        notificaciones = {n['clave']: n for n in datos['notificaciones']}
        self.assertIn('ventas_pendientes', notificaciones)
        self.assertEqual(notificaciones['ventas_pendientes']['url'], reverse('ventas'))
