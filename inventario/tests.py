from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from animales.models import Animal
from finanzas.models import Compra
from inventario.models import ComposicionDieta, Consumo, DetalleCompra, Dieta, Insumo, Lote
from sanidad.models import EventoSanitario
from usuarios.models import Veterinario


class InsumoCrudTests(TestCase):
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
            animal=animal,
            veterinario=veterinario,
        )
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
