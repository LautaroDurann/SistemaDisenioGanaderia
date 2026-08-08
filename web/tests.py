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

from animales.models import Animal, MovimientoAnimal, Pesaje
from establecimientos.models import Establecimiento, Parcela
from finanzas.models import Compra, MovimientoFinanciero, Venta
from sanidad.models import DetalleEvento, EventoSanitario
from usuarios.models import Comprador, Persona, RolEstablecimiento, Usuario


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
        for url_name in ('dashboard', 'stock', 'movimientos', 'potreros', 'vacunacion', 'sanidad', 'pesajes', 'alimentacion', 'usuarios', 'configuracion'):
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_pagina_usuarios_incluye_datos_ganastock(self):
        response = self.client.get(reverse('usuarios'))
        self.assertContains(response, 'ganastock-data-usuarios')
        self.assertContains(response, 'ganastock-data-establecimientos')
        self.assertContains(response, 'window.GANASTOCK_DATA')
        self.assertContains(response, 'propietario')
        self.assertContains(response, 'Campo de prueba')
        contenido = response.content.decode()
        inicio = contenido.index('id="ganastock-data-establecimientos"') 
        inicio = contenido.index('>', inicio) + 1
        fin = contenido.index('</script>', inicio)
        establecimientos = json.loads(contenido[inicio:fin])
        self.assertEqual([e['nombre'] for e in establecimientos], ['Campo de prueba'])

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
                        'tab-potreros', 'tab-usuarios-roles', 'tabla-categorias',
                        'tabla-vacunas', 'tabla-estados-potrero', 'modalListaSimple'):
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

    def test_eliminar_establecimiento_borra_dependencias(self):
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

        self.assertFalse(Establecimiento.objects.filter(pk=segundo.id).exists())
        self.assertFalse(Parcela.objects.filter(pk=parcela_segunda.id).exists())
        self.assertFalse(RolEstablecimiento.objects.filter(pk=rol.id).exists())
        animal.refresh_from_db()
        self.assertIsNone(animal.establecimiento)
        self.assertIsNone(animal.parcela)
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
        self.assertEqual(self.client.get(reverse('usuarios')).status_code, 302)
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
