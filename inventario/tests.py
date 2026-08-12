from datetime import date
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from animales.models import Animal
from establecimientos.models import Establecimiento
from finanzas.models import Compra
from inventario.models import Consumo, DetalleCompra, Insumo, Lote
from sanidad.models import DetalleEvento, EventoSanitario
from usuarios.models import Persona, RolEstablecimiento, Usuario, Veterinario


class InsumoCrudTests(TestCase):
    def setUp(self):
        establecimiento = Establecimiento.objects.create(
            nombre='Campo insumos', fecha_inicio=date.today(), ubicacion='Córdoba'
        )
        self.establecimiento = establecimiento
        persona = Persona.objects.create(
            nombre='Juan', apellido='Fernandez', correo_electronico='juan-insumos@test.com',
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

    def test_model_creates_insumo_with_tipo_and_lote(self):
        insumo = Insumo.objects.create(
            nombre='Vacuna antiaftosa',
            tipo='Vacuna',
            unidadDeMedida='ml',
        )
        lote = Lote.objects.create(
            insumo=insumo,
            fechaVencimiento=date(2026, 12, 31),
            stockActual=Decimal('100.00'),
        )

        self.assertEqual(insumo.tipo, 'Vacuna')
        self.assertEqual(insumo.nombre, 'Vacuna antiaftosa')
        self.assertEqual(lote.insumo, insumo)
        self.assertEqual(lote.stockActual, Decimal('100.00'))

        with self.assertRaises(AttributeError):
            getattr(insumo, 'stockActual')

    def test_lote_is_used_in_detalle_compra_and_consumo(self):
        insumo = Insumo.objects.create(nombre='Medicamento A', tipo='Medicamento', unidadDeMedida='ml')
        lote = Lote.objects.create(insumo=insumo, fechaVencimiento=date(2027, 1, 15), stockActual=Decimal('50.00'))
        compra = Compra.objects.create(tipo='Insumos', fecha=date(2026, 1, 1), monto_total=Decimal('100.00'))
        detalle = DetalleCompra.objects.create(compra=compra, lote=lote, cantidad=Decimal('10.00'), precioUnitario=Decimal('10.00'))
        veterinario = Veterinario.objects.create(
            dni='12345679',
            nombre='Ana',
            apellido='Perez',
            correo_electronico='ana-lote-unique@example.com',
            fecha_nacimiento=date(1990, 1, 1),
            telefono='1234',
        )
        animal = Animal.objects.create(
            tipo_animal='Bovino',
            sexo='Hembra',
            nombre='Animal prueba',
            vivo=True,
        )
        evento = EventoSanitario.objects.create(
            detalle='Aplicación',
            tipo='Vacunación',
            fecha_aplicacion=date(2026, 1, 2),
            costo_total=Decimal('20.00'),
            veterinario=veterinario,
        )
        DetalleEvento.objects.create(evento=evento, animal=animal)
        consumo = Consumo.objects.create(lote=lote, evento_sanitario=evento, cantidad=Decimal('5.00'))

        self.assertEqual(detalle.lote, lote)
        self.assertEqual(consumo.lote, lote)

    def test_api_can_create_and_update_insumos(self):
        create_response = self.client.post(
            reverse('insumos_api'),
            {
                'nombre': 'Medicamento A',
                'tipo': 'Medicamento',
                'unidadDeMedida': 'ml',
            },
        )

        self.assertEqual(create_response.status_code, 201)
        created_data = create_response.json()['insumo']
        insumo_id = created_data['id']
        self.assertEqual(created_data['cantidad_total'], '0.00')
        self.assertFalse(Lote.objects.filter(insumo__id=insumo_id).exists())

        update_response = self.client.post(
            reverse('insumo_detalle', args=[insumo_id]),
            {
                'nombre': 'Medicamento A Editado',
                'tipo': 'Medicamento',
                'unidadDeMedida': 'ml',
            },
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()['insumo']['nombre'], 'Medicamento A Editado')

        delete_response = self.client.delete(reverse('insumo_detalle', args=[insumo_id]))
        self.assertEqual(delete_response.status_code, 200)
        # La baja es lógica: el insumo queda oculto pero no se borra.
        self.assertTrue(Insumo.objects.filter(pk=insumo_id, activo=False).exists())
        self.assertFalse(Insumo.objects.filter(pk=insumo_id, activo=True).exists())
        self.assertNotIn(insumo_id, [i['id'] for i in self.client.get(reverse('insumos_api')).json()['insumos']])

    def test_api_insumo_detail_returns_lotes(self):
        insumo = Insumo.objects.create(nombre='Otro insumo', tipo='Otros', unidadDeMedida='kg')
        Lote.objects.create(insumo=insumo, nombre='Lote 1', fechaVencimiento=date(2026, 12, 1),
                            stockActual=Decimal('50.00'), establecimiento=self.establecimiento)
        Lote.objects.create(insumo=insumo, nombre='Lote 2', fechaVencimiento=date(2026, 12, 15),
                            stockActual=Decimal('100.00'), establecimiento=self.establecimiento)

        response = self.client.get(reverse('insumo_detalle', args=[insumo.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()['insumo']
        self.assertEqual(payload['cantidad_total'], '150.00')
        self.assertEqual(len(payload['lotes']), 2)
        self.assertEqual(payload['lotes'][0]['nombre'], 'Lote 1')

    def _crear_historial(self, insumo, lote):
        """Crea compra y evento sanitario (con consumo) asociados al lote."""
        compra = Compra.objects.create(
            tipo='Insumos', fecha=date(2026, 1, 1), monto_total=Decimal('100.00'),
        )
        detalle = DetalleCompra.objects.create(
            compra=compra, lote=lote, cantidad=Decimal('10.00'), precioUnitario=Decimal('10.00'),
        )
        veterinario = Veterinario.objects.create(
            dni='12345678', nombre='Ana', apellido='Perez',
            correo_electronico='ana-historial@example.com', fecha_nacimiento=date(1990, 1, 1),
            telefono='1234',
        )
        animal = Animal.objects.create(tipo_animal='Bovino', sexo='Hembra', nombre='Vaca 1', vivo=True)
        evento = EventoSanitario.objects.create(
            detalle='Aplicación', tipo='Vacunación', fecha_aplicacion=date(2026, 1, 2),
            costo_total=Decimal('20.00'), veterinario=veterinario,
        )
        DetalleEvento.objects.create(evento=evento, animal=animal)
        consumo = Consumo.objects.create(lote=lote, evento_sanitario=evento, cantidad=Decimal('5.00'))
        EventoSanitario.objects.filter(pk=evento.pk).update(lote=lote)
        evento.refresh_from_db()
        return {'compra': compra, 'detalle': detalle, 'evento': evento,
                'consumo': consumo}

    def test_baja_logica_insumo_conserva_historial(self):
        insumo = Insumo.objects.create(nombre='Vacuna historica', tipo='Vacuna', unidadDeMedida='dosis')
        lote = Lote.objects.create(insumo=insumo, nombre='Lote A', stockActual=Decimal('50.00'),
                                   establecimiento=self.establecimiento)
        historial = self._crear_historial(insumo, lote)

        response = self.client.delete(reverse('insumo_detalle', args=[insumo.id]))
        self.assertEqual(response.status_code, 200)

        # El insumo queda oculto pero no se borra.
        self.assertTrue(Insumo.objects.filter(pk=insumo.id, activo=False).exists())
        # Su historial queda intacto.
        self.assertTrue(Lote.objects.filter(pk=lote.pk, activo=True).exists())
        self.assertTrue(DetalleCompra.objects.filter(pk=historial['detalle'].pk).exists())
        self.assertTrue(Consumo.objects.filter(pk=historial['consumo'].pk).exists())
        self.assertEqual(historial['evento'].lote_id, lote.id)
        # No aparece en los listados activos.
        self.assertNotIn(insumo.id, [i['id'] for i in self.client.get(reverse('insumos_api')).json()['insumos']])
        self.assertEqual(self.client.get(reverse('insumo_detalle', args=[insumo.id])).status_code, 404)

    def test_baja_logica_lote_conserva_historial(self):
        insumo = Insumo.objects.create(nombre='Medicamento historico', tipo='Medicamento', unidadDeMedida='ml')
        lote = Lote.objects.create(insumo=insumo, nombre='Lote B', stockActual=Decimal('30.00'),
                                   establecimiento=self.establecimiento)
        historial = self._crear_historial(insumo, lote)

        response = self.client.delete(reverse('lote_detalle', args=[lote.id]))
        self.assertEqual(response.status_code, 200)

        # El lote queda oculto pero no se borra.
        self.assertTrue(Lote.objects.filter(pk=lote.pk, activo=False).exists())
        # Su historial queda intacto.
        self.assertTrue(DetalleCompra.objects.filter(pk=historial['detalle'].pk).exists())
        self.assertTrue(Consumo.objects.filter(pk=historial['consumo'].pk).exists())
        self.assertEqual(historial['evento'].lote_id, lote.id)
        # No aparece en el detalle del insumo ni se puede acceder.
        payload = self.client.get(reverse('insumo_detalle', args=[insumo.id])).json()['insumo']
        self.assertEqual(payload['lotes'], [])
        self.assertEqual(self.client.get(reverse('lote_detalle', args=[lote.id])).status_code, 404)
