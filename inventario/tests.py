from datetime import date
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from animales.models import Animal
from establecimientos.models import Establecimiento
from finanzas.models import Compra
from inventario.models import ComposicionDieta, Consumo, DetalleCompra, Dieta, Insumo, Lote
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

    def test_lote_is_used_in_detalle_compra_consumo_and_dieta(self):
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
        dieta = Dieta.objects.create(nombre='Dieta prueba')
        composicion = ComposicionDieta.objects.create(lote=lote, dieta=dieta, cantidadPorPorcion=Decimal('2.00'))

        self.assertEqual(detalle.lote, lote)
        self.assertEqual(consumo.lote, lote)
        self.assertEqual(composicion.lote, lote)

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
        self.assertFalse(Insumo.objects.filter(pk=insumo_id).exists())

    def test_api_insumo_detail_returns_lotes(self):
        insumo = Insumo.objects.create(nombre='Alimento B', tipo='Alimento', unidadDeMedida='kg')
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
