"""Carga un dataset de demostración realista y coherente para todo el sistema.

Uso:
    python manage.py seed_demo --reset

Con --reset vacía la base (flush) antes de cargar los datos. Sin la bandera
solo se cargan los registros que no existan todavía.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from animales.models import Animal, Parto, Preniez
from establecimientos.models import Establecimiento, Parcela
from finanzas.models import Compra, LiquidacionSueldo, MovimientoFinanciero, Venta
from inventario.models import DetalleCompra, Insumo, Lote
from sanidad.models import DetalleEvento, Diagnostico, Enfermedad, EventoSanitario
from usuarios.models import Comprador, Persona, Proveedor, RolEstablecimiento, Usuario, Veterinario


def _dec(value):
    return Decimal(str(value))


def _cuantizar(valor):
    return valor.quantize(Decimal('0.01'))


class Command(BaseCommand):
    help = 'Carga un dataset de demostración realista (animales, ventas, gastos, insumos, sanidad y preñeces).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Vacía la base de datos antes de cargar el dataset.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Vaciando la base de datos...')
            call_command('flush', interactive=False)
            self.stdout.write('Base vaciada.')

        estancia = self._crear_establecimiento()
        parcelas = self._crear_parcelas(estancia)
        veterinaria, proveedores, compradores = self._crear_terceros()
        usuario_propietario, usuario_operario = self._crear_usuarios(estancia)
        insumos, lotes = self._crear_insumos(estancia)

        animales = self._crear_animales(estancia, parcelas)
        self._crear_compras(estancia, proveedores, insumos, lotes, animales)
        evento_inseminacion = self._crear_eventos_sanitarios(estancia, veterinaria, lotes, animales)
        self._crear_ventas(estancia, compradores, animales)
        self._crear_prenieces(evento_inseminacion, animales)
        self._crear_liquidaciones(estancia, usuario_operario)
        self._crear_sanidad(animales)

        self._resumen(estancia, usuario_propietario, usuario_operario)

    # ------------------------------------------------------------------
    # Establecimiento
    # ------------------------------------------------------------------
    def _crear_establecimiento(self):
        estancia, _ = Establecimiento.objects.get_or_create(
            nombre='Estancia Los Algarrobos',
            defaults={
                'fecha_inicio': date(2016, 3, 15),
                'ubicacion': 'Ruta 95 km 42, Presidencia Roque Sáenz Peña, Chaco',
            },
        )
        return estancia

    def _crear_parcelas(self, estancia):
        parcelas = {}
        datos = [
            ('Potrero Norte', 350, 620, Parcela.ESTADO_EN_PASTOREO),
            ('Potrero Sur', 300, 540, Parcela.ESTADO_EN_PASTOREO),
            ('Bajos del Este', 250, 400, Parcela.ESTADO_EN_PASTOREO),
            ('Potrero de Cría', 280, 450, Parcela.ESTADO_EN_PASTOREO),
            ('Cuarentena', 100, 150, Parcela.ESTADO_EN_DESCANSO),
            ('Invernada Oeste', 320, 480, Parcela.ESTADO_EN_MANTENIMIENTO),
        ]
        for nombre, ancho, largo, estado in datos:
            parcela, _ = Parcela.objects.get_or_create(
                establecimiento=estancia,
                descripcion=nombre,
                defaults={'ancho': ancho, 'largo': largo, 'estado': estado},
            )
            parcelas[nombre] = parcela
        return parcelas

    # ------------------------------------------------------------------
    # Personas, usuarios y terceros
    # ------------------------------------------------------------------
    def _crear_usuarios(self, estancia):
        propietario = self._get_or_create_usuario(
            nombre_usuario='Lautaro', clave='lautaro123',
            nombre='Lautaro', apellido='Duran', dni='30123456',
            correo='lautaro@algarrobos.com.ar', telefono='3644-551122',
            rol='Propietario', establecimiento=estancia, debe_cambiar_clave=False,
        )
        operario = self._get_or_create_usuario(
            nombre_usuario='pedro', clave='pedro123',
            nombre='Pedro', apellido='Gómez', dni='35111222',
            correo='pedro.gomez@algarrobos.com.ar', telefono='3644-556677',
            rol='Operario', establecimiento=estancia, debe_cambiar_clave=True,
        )
        return propietario, operario

    def _get_or_create_usuario(self, nombre_usuario, clave, nombre, apellido, dni, correo, telefono, rol, establecimiento, debe_cambiar_clave):
        usuario = Usuario.objects.filter(nombre_usuario=nombre_usuario).first()
        if usuario is None:
            persona = Persona.objects.create(
                nombre=nombre, apellido=apellido, dni=dni,
                correo_electronico=correo, telefono=telefono,
            )
            usuario = Usuario.objects.create(
                nombre_usuario=nombre_usuario,
                clave=make_password(clave),
                persona=persona,
                debe_cambiar_clave=debe_cambiar_clave,
            )
            RolEstablecimiento.objects.create(
                usuario=usuario,
                establecimiento=establecimiento,
                nombre=rol,
                fecha_ingreso=establecimiento.fecha_inicio,
                estado_acceso=True,
            )
        return usuario

    def _crear_terceros(self):
        veterinaria = Veterinario.objects.create(
            nombre='Marcela', apellido='Ibarra', dni='27345678',
            correo_electronico='mibarra@vet.com.ar', telefono='3644-500111',
        )
        proveedores = [
            Proveedor.objects.create(nombre='AgroVeterinaria Norte', dni='30555666', telefono='3644-511223'),
            Proveedor.objects.create(nombre='Cooperativa Ganadera del Impenetrable', dni='30777888', telefono='3644-522334'),
            Proveedor.objects.create(nombre='Ferretería El Agrario', dni='23333444', telefono='3644-533445'),
        ]
        compradores = [
            Comprador.objects.create(nombre='Frigorífico Algarrobo SA', dni='30999111', telefono='3644-544556'),
            Comprador.objects.create(nombre='Consignataria La Rural SRL', dni='30666677', telefono='3644-555667'),
            Comprador.objects.create(nombre='Abasto del Norte', dni='27222333', telefono='3644-566778'),
        ]
        return veterinaria, proveedores, compradores

    # ------------------------------------------------------------------
    # Insumos y lotes
    # ------------------------------------------------------------------
    def _crear_insumos(self, estancia):
        datos = [
            ('Aftosa SENASA', 'Dosis', 'Vacuna'),
            ('Ivermectina 1%', 'ml', 'Medicamento'),
            ('Oxitetraciclina LA', 'ml', 'Medicamento'),
            ('Complejo Vitamínico ADE', 'ml', 'Medicamento'),
            ('Balanceado para terneros', 'kg', 'Otros'),
            ('Suplemento mineral', 'kg', 'Otros'),
        ]
        insumos = {}
        for nombre, unidad, tipo in datos:
            insumo, _ = Insumo.objects.get_or_create(
                nombre=nombre, defaults={'unidadDeMedida': unidad, 'tipo': tipo},
            )
            insumos[nombre] = insumo

        # (insumo, nombre_lote, vencimiento, stock inicial)
        datos_lotes = [
            (insumos['Aftosa SENASA'], 'AF-2601', date(2026, 7, 10), 50),
            (insumos['Aftosa SENASA'], 'AF-2611', date(2027, 1, 15), 40),
            (insumos['Ivermectina 1%'], 'IV-2605', date(2027, 5, 20), 500),
            (insumos['Oxitetraciclina LA'], 'OX-2604', date(2026, 11, 30), 300),
            (insumos['Complejo Vitamínico ADE'], 'AD-2602', date(2026, 9, 5), 200),
            (insumos['Balanceado para terneros'], 'BL-2603', date(2026, 12, 10), 80),
            (insumos['Suplemento mineral'], 'SM-2606', date(2027, 3, 1), 150),
        ]
        lotes = {}
        for insumo, nombre, vencimiento, stock in datos_lotes:
            lote = Lote.objects.create(
                insumo=insumo, nombre=nombre, fechaVencimiento=vencimiento,
                stockActual=stock, establecimiento=estancia,
            )
            lotes[nombre] = lote
        return insumos, lotes

    # ------------------------------------------------------------------
    # Animales
    # ------------------------------------------------------------------
    def _crear_animal(self, caravana, nombre, tipo_animal, sexo, raza, color,
                      nacimiento, peso_actual, parcela, establecimiento,
                      madre=None, padre=None, costo=None, castrado=False,
                      vivo=True, fecha_muerte=None, enfermo=False,
                      parto=None, peso_nacer=30, peso_destete=None):
        animal = Animal.objects.create(
            id_senasa=caravana, nombre=nombre, tipo_animal=tipo_animal,
            sexo=sexo, raza=raza, color=color,
            fecha_nacimiento=nacimiento, peso_actual=_dec(peso_actual),
            peso_al_nacer=_dec(peso_nacer) if peso_nacer is not None else None,
            peso_al_destete=_dec(peso_destete) if peso_destete is not None else None,
            costo_adquisicion=costo, parcela=parcela,
            establecimiento=establecimiento, madre=madre, padre=padre,
            castrado=castrado, vivo=vivo, fecha_muerte=fecha_muerte,
            enfermo=enfermo, parto=parto,
        )
        return animal

    def _crear_animales(self, estancia, parcelas):
        animales = {}
        norte = parcelas['Potrero Norte']
        sur = parcelas['Potrero Sur']
        bajos = parcelas['Bajos del Este']
        cria = parcelas['Potrero de Cría']
        invernada = parcelas['Invernada Oeste']
        cuarentena = parcelas['Cuarentena']

        # --- Toros ---
        don_julio = self._crear_animal(
            '1200100001', 'Don Julio', 'Bovino', 'Macho', 'Braford', 'Colorado',
            date(2018, 11, 20), 860, norte, estancia, costo=_dec('2400000.00'),
        )
        changüi = self._crear_animal(
            '1200100002', 'Changüí', 'Bovino', 'Macho', 'Brahman', 'Blanco',
            date(2021, 2, 14), 780, norte, estancia,
        )
        animales['don_julio'] = don_julio
        animales['changüi'] = changüi

        # --- Vacas ---
        vacas = [
            ('1200100101', 'Paloma', 'Braford', 'Colorado', date(2019, 9, 15), 515, norte),
            ('1200100102', 'Luna', 'Angus', 'Negro', date(2020, 4, 3), 505, sur),
            ('1200100103', 'Mora', 'Braford', 'Overo', date(2018, 8, 22), 540, norte),
            ('1200100104', 'Nina', 'Hereford', 'Colorado', date(2021, 1, 18), 495, sur),
            ('1200100105', 'Aurora', 'Angus', 'Negro', date(2019, 11, 30), 530, bajos),
            ('1200100106', 'Canela', 'Braford', 'Colorado', date(2020, 7, 11), 505, bajos),
            ('1200100107', 'Dulce', 'Brangus', 'Barcino', date(2018, 5, 25), 555, invernada),
            ('1200100108', 'Estrella', 'Hereford', 'Colorado', date(2021, 3, 7), 480, cria),
            ('1200100109', 'Flora', 'Angus', 'Negro', date(2020, 10, 19), 515, cria),
            ('1200100110', 'Gringa', 'Braford', 'Colorado', date(2019, 2, 10), 545, sur),
            ('1200100111', 'Jacinta', 'Brangus', 'Barcino', date(2021, 6, 28), 470, cria),
            ('1200100112', 'Lucía', 'Hereford', 'Colorado', date(2018, 12, 5), 550, sur),
            ('1200100113', 'Mancha', 'Braford', 'Overo', date(2020, 1, 29), 525, invernada),
            ('1200100114', 'Violeta', 'Braford', 'Colorado', date(2019, 3, 31), 550, invernada),
        ]
        for caravana, nombre, raza, color, nacimiento, peso, parcela in vacas:
            animales[nombre] = self._crear_animal(
                caravana, nombre, 'Bovino', 'Hembra', raza, color,
                nacimiento, peso, parcela, estancia, peso_destete=200,
            )

        # --- Novillos (para venta) ---
        novillos = [
            ('1200100201', 'Tordillo', 'Braford', 'Colorado', date(2024, 2, 10), 380, norte),
            ('1200100202', 'Pampa', 'Angus', 'Negro', date(2024, 3, 5), 395, sur),
            ('1200100203', 'Boleto', 'Hereford', 'Colorado', date(2024, 1, 22), 410, bajos),
            ('1200100204', 'Chimango', 'Braford', 'Colorado', date(2024, 4, 14), 390, norte),
            ('1200100205', 'Fierro', 'Brangus', 'Barcino', date(2024, 2, 28), 420, invernada),
            ('1200100206', 'Titán', 'Angus', 'Negro', date(2024, 5, 2), 405, sur),
        ]
        for caravana, nombre, raza, color, nacimiento, peso, parcela in novillos:
            animales[nombre] = self._crear_animal(
                caravana, nombre, 'Bovino', 'Macho', raza, color,
                nacimiento, peso, parcela, estancia, castrado=True, peso_destete=200,
            )

        # --- Terneros / terneras al pie ---
        terneros = [
            ('1200100301', 'Pitufo', 'Macho', 'Braford', 'Colorado', date(2026, 2, 18), 185, norte, 'Paloma'),
            ('1200100302', 'Rosita', 'Hembra', 'Braford', 'Colorado', date(2026, 3, 16), 155, norte, 'Mora'),
            ('1200100303', 'Bombón', 'Macho', 'Angus', 'Negro', date(2026, 3, 27), 165, bajos, 'Aurora'),
            ('1200100304', 'Chinita', 'Hembra', 'Angus', 'Negro', date(2026, 4, 28), 130, sur, 'Gringa'),
            ('1200100305', 'Nube', 'Hembra', 'Hereford', 'Colorado', date(2026, 4, 3), 145, cria, 'Estrella'),
            ('1200100306', 'Tero', 'Macho', 'Brangus', 'Barcino', date(2026, 5, 22), 120, cria, 'Jacinta'),
            ('1200100307', 'Ambar', 'Hembra', 'Braford', 'Colorado', date(2026, 5, 17), 115, invernada, 'Mancha'),
            ('1200100308', 'Coco', 'Macho', 'Braford', 'Overo', date(2026, 7, 1), 85, norte, None),
        ]
        for caravana, nombre, sexo, raza, color, nacimiento, peso, parcela, madre in terneros:
            animales[nombre] = self._crear_animal(
                caravana, nombre, 'Bovino', sexo, raza, color,
                nacimiento, peso, parcela, estancia,
                madre=animales[madre] if madre else None,
                padre=don_julio,
            )

        # --- Animales muertos (historia) ---
        self._crear_animal(
            '1200100401', 'Abuela', 'Bovino', 'Hembra', 'Angus', 'Negro',
            date(2015, 3, 20), 480, norte, estancia,
            vivo=False, fecha_muerte=date(2026, 2, 10),
        )
        self._crear_animal(
            '1200100402', 'Pichón', 'Bovino', 'Macho', 'Hereford', 'Colorado',
            date(2026, 6, 12), 90, sur, estancia,
            vivo=False, fecha_muerte=date(2026, 7, 20),
        )

        # --- Ovinos ---
        ovejas = [
            ('1300100501', 'Copetona', date(2021, 3, 10), 62, sur),
            ('1300100502', 'Zaraza', date(2022, 5, 1), 58, sur),
            ('1300100503', 'Mona', date(2021, 11, 15), 65, bajos),
            ('1300100504', 'Blanca', date(2022, 2, 20), 60, bajos),
        ]
        for caravana, nombre, nacimiento, peso, parcela in ovejas:
            animales[nombre] = self._crear_animal(
                caravana, nombre, 'Ovino', 'Hembra', 'Corriedale', 'Blanco',
                nacimiento, peso, parcela, estancia, peso_nacer=4, peso_destete=18,
            )
        caruso = self._crear_animal(
            '1300100505', 'Caruso', 'Ovino', 'Macho', 'Corriedale', 'Blanco',
            date(2020, 9, 12), 95, sur, estancia,
        )
        animales['caruso'] = caruso
        corderos = [
            ('1300100506', 'Algodón', 'Macho', date(2026, 4, 20), 38, 'Copetona'),
            ('1300100507', 'Perla', 'Hembra', date(2026, 4, 25), 35, 'Zaraza'),
        ]
        for caravana, nombre, sexo, nacimiento, peso, madre in corderos:
            animales[nombre] = self._crear_animal(
                caravana, nombre, 'Ovino', sexo, 'Corriedale', 'Blanco',
                nacimiento, peso, sur, estancia,
                madre=animales[madre], padre=caruso, peso_nacer=4,
            )

        # --- Porcinos ---
        cerdas = [
            ('1400100601', 'Chanchita', date(2021, 4, 15), 150, bajos),
            ('1400100602', 'Rosa', date(2022, 7, 30), 145, bajos),
            ('1400100603', 'Negra', date(2021, 12, 5), 160, bajos),
        ]
        for caravana, nombre, nacimiento, peso, parcela in cerdas:
            animales[nombre] = self._crear_animal(
                caravana, nombre, 'Porcino', 'Hembra', 'Duroc', 'Rosada',
                nacimiento, peso, parcela, estancia, peso_nacer=1.5, peso_destete=20,
            )
        animales['padrillo'] = self._crear_animal(
            '1400100604', 'Padrillo', 'Porcino', 'Macho', 'Duroc', 'Rosada',
            date(2020, 6, 1), 180, bajos, estancia,
        )
        capones = [
            ('1400100605', 'Gordo', date(2025, 3, 15), 110),
            ('1400100606', 'Tito', date(2025, 5, 20), 95),
        ]
        for caravana, nombre, nacimiento, peso in capones:
            animales[nombre] = self._crear_animal(
                caravana, nombre, 'Porcino', 'Macho', 'Criollo', 'Negro',
                nacimiento, peso, bajos, estancia, castrado=True,
            )

        # Animal enfermo (dispara la alerta del dashboard).
        animales['Estrella'].enfermo = True
        animales['Estrella'].save(update_fields=['enfermo'])
        return animales

    # ------------------------------------------------------------------
    # Compras (gastos)
    # ------------------------------------------------------------------
    def _crear_compras(self, estancia, proveedores, insumos, lotes, animales):
        agro, cooperativa, ferreteria = proveedores

        # 1. Vacuna aftosa (50 dosis, lote que quedará vencido con saldo).
        self._crear_compra_insumos(
            estancia, agro, date(2026, 2, 12), 'Pagada', 'Efectivo',
            'Recarga de vacuna aftosa para la campaña de otoño.',
            insumos['Aftosa SENASA'], lotes['AF-2601'], 50, _dec('1500.00'),
        )
        # 2. Vacuna aftosa (lote vigente).
        self._crear_compra_insumos(
            estancia, agro, date(2026, 8, 1), 'Pagada', 'Transferencia',
            'Nuevo lote de aftosa para la campaña de primavera.',
            insumos['Aftosa SENASA'], lotes['AF-2611'], 40, _dec('1580.00'),
        )
        # 3. Ivermectina.
        self._crear_compra_insumos(
            estancia, agro, date(2026, 5, 14), 'Pagada', 'Transferencia',
            'Antiparasitario para desparasitación de hacienda.',
            insumos['Ivermectina 1%'], lotes['IV-2605'], 500, _dec('950.00'),
        )
        # 4. Balanceado para terneros.
        self._crear_compra_insumos(
            estancia, cooperativa, date(2026, 6, 5), 'Pagada', 'Efectivo',
            'Balanceado de crecimiento para terneros al pie.',
            insumos['Balanceado para terneros'], lotes['BL-2603'], 80, _dec('650.00'),
        )
        # 5. Reproductor Brahman (compra de animal).
        compra_reproductor = Compra.objects.create(
            tipo='Animales', fecha=date(2026, 4, 5),
            monto_total=_dec('2850000.00'), detalle='Reproductor Brahman registrado (Changüí).',
            proveedor=cooperativa, estadoDePago='Pagada', metodoDePago='Transferencia',
        )
        changüi = animales['changüi']
        changüi.compra = compra_reproductor
        changüi.costo_adquisicion = compra_reproductor.monto_total
        changüi.save(update_fields=['compra', 'costo_adquisicion'])
        self._crear_movimiento_compra(estancia, compra_reproductor)

        # 6. Maquinaria (pendiente de pago).
        compra_maquinaria = Compra.objects.create(
            tipo='Maquinaria', fecha=date(2026, 8, 5),
            monto_total=_dec('3200000.00'),
            detalle='Moto niveladora usada para el mantenimiento de calles internas.',
            proveedor=ferreteria, estadoDePago='Pendiente', metodoDePago='Cheque',
        )
        self._crear_movimiento_compra(estancia, compra_maquinaria)

        # 7. Alambrados (Otros).
        compra_otra = Compra.objects.create(
            tipo='Otros', fecha=date(2026, 3, 20),
            monto_total=_dec('480000.00'),
            detalle='Alambre, postes y tranqueras para el potrero de cría.',
            proveedor=ferreteria, estadoDePago='Pagada', metodoDePago='Efectivo',
        )
        self._crear_movimiento_compra(estancia, compra_otra)

    def _crear_compra_insumos(self, estancia, proveedor, fecha, estado_pago, metodo,
                              detalle, insumo, lote, cantidad, precio_unitario):
        monto = _cuantizar(_dec(cantidad) * precio_unitario)
        compra = Compra.objects.create(
            tipo='Insumos', fecha=fecha, monto_total=monto, detalle=detalle,
            proveedor=proveedor, estadoDePago=estado_pago, metodoDePago=metodo,
        )
        DetalleCompra.objects.create(
            compra=compra, lote=lote, cantidad=_dec(cantidad), precioUnitario=precio_unitario,
        )
        self._crear_movimiento_compra(estancia, compra)

    def _crear_movimiento_compra(self, estancia, compra):
        movimiento = MovimientoFinanciero.objects.create(
            tipo='Egreso', nombre=f'Compra #{compra.id} - {compra.tipo}',
            monto_total=compra.monto_total, fecha=compra.fecha,
            detalle=compra.detalle, establecimiento=estancia,
        )
        compra.mov_financiero = movimiento
        compra.save(update_fields=['mov_financiero'])

    # ------------------------------------------------------------------
    # Ventas
    # ------------------------------------------------------------------
    def _crear_ventas(self, estancia, compradores, animales):
        datos = [
            # (fecha, precio_por_kg, desbaste, estado, metodo, comprador, detalle, animales)
            (
                date(2026, 3, 10), _dec('3200.00'), _dec('4.00'),
                'Pagada', 'Transferencia', compradores[0],
                'Venta de novillos gordos de invernada.',
                ['Tordillo', 'Pampa', 'Boleto'],
            ),
            (
                date(2026, 6, 18), _dec('3500.00'), _dec('3.00'),
                'Pagada', 'Efectivo', compradores[1],
                'Venta de novillos con destino a faena.',
                ['Chimango', 'Titán'],
            ),
            (
                date(2026, 8, 1), _dec('3300.00'), _dec('2.00'),
                'Pendiente', 'Cheque', compradores[2],
                'Venta de novillo Braford con entrega diferida.',
                ['Fierro'],
            ),
        ]
        for fecha, precio_kg, desbaste, estado, metodo, comprador, detalle, nombres in datos:
            lista = [animales[nombre] for nombre in nombres]
            peso_total = sum((a.peso_actual or _dec('0')) for a in lista)
            factor = _dec('1') - desbaste / _dec('100')
            peso_desbastado = _cuantizar(peso_total * factor)
            monto_total = _cuantizar(peso_desbastado * precio_kg)

            venta = Venta.objects.create(
                tipo='Venta de ganado', fecha=fecha, peso_total=peso_total,
                porcentajeDesbaste=desbaste, precio_por_kg=precio_kg,
                monto_total=monto_total, detalle=detalle,
                comprador=comprador, estadoDeCobro=estado, metodoDePago=metodo,
            )
            movimiento = MovimientoFinanciero.objects.create(
                tipo='Ingreso', nombre=f'Venta #{venta.id}',
                monto_total=monto_total, fecha=fecha,
                detalle=detalle or f'Venta de {len(lista)} animal(es).',
                establecimiento=estancia,
            )
            venta.mov_financiero = movimiento
            venta.save(update_fields=['mov_financiero'])

            for animal in lista:
                precio_venta_animal = _cuantizar(animal.peso_actual * factor * precio_kg)
                animal.vendido = True
                animal.venta = venta
                animal.precio_venta = precio_venta_animal
                animal.save(update_fields=['vendido', 'venta', 'precio_venta'])

    # ------------------------------------------------------------------
    # Eventos sanitarios (incluye la inseminación)
    # ------------------------------------------------------------------
    def _crear_eventos_sanitarios(self, estancia, veterinaria, lotes, animales):
        # Bovinos nacidos antes de 2026 (adultos y novillos) para la campaña de febrero.
        adultos = Animal.objects.filter(
            tipo_animal='Bovino', vivo=True, fecha_nacimiento__lt=date(2026, 1, 1),
        ).exclude(id_senasa='1200100401')

        # 1. Vacunación aftosa aplicada (descuenta stock del lote que quedará vencido).
        n_aftosa = adultos.count()
        evento_vacunacion = EventoSanitario.objects.create(
            tipo='Vacunación', fecha_aplicacion=date(2026, 2, 20),
            estado=True, detalle='Campaña de vacunación contra la fiebre aftosa.',
            veterinario=veterinaria, lote=lotes['AF-2601'],
            cantidad=_dec(n_aftosa), costo_total=_cuantizar(_dec(n_aftosa) * _dec('1000.00')),
            costo_servicio=_dec('20000.00'),
        )
        for animal in adultos:
            DetalleEvento.objects.create(evento=evento_vacunacion, animal=animal, cantidad_dosis=_dec('1'))
        self._crear_movimiento_evento(estancia, evento_vacunacion)

        # 2. Vacunación aftosa programada (pendiente, dispara la alerta).
        # No incluye los novillos: se venden antes de la fecha del evento.
        bovinos_hoy = Animal.objects.filter(
            tipo_animal='Bovino', vivo=True,
        ).exclude(id_senasa__in=[
            '1200100401', '1200100402',
            '1200100201', '1200100202', '1200100203',
            '1200100204', '1200100205', '1200100206',
        ])
        evento_programado = EventoSanitario.objects.create(
            tipo='Vacunación', fecha_aplicacion=date(2026, 8, 25),
            estado=False, detalle='Refuerzo de aftosa - próximo calendario.',
            veterinario=veterinaria,
        )
        for animal in bovinos_hoy:
            DetalleEvento.objects.create(evento=evento_programado, animal=animal, cantidad_dosis=_dec('1'))

        # 3. Desparasitación (bovinos adultos y ovinos adultos).
        # En abril los novillos Tordillo/Pampa/Boleto ya se vendieron (marzo).
        desparasitados = Animal.objects.filter(
            tipo_animal='Bovino', vivo=True, fecha_nacimiento__lt=date(2026, 1, 1),
        ).exclude(id_senasa__in=[
            '1200100401', '1200100201', '1200100202', '1200100203',
        ]).values_list('idAnimal', flat=True) | Animal.objects.filter(
            tipo_animal='Ovino', vivo=True, fecha_nacimiento__lt=date(2026, 1, 1),
        ).values_list('idAnimal', flat=True)
        n_desparasitados = len(list(desparasitados))
        evento_desparasitacion = EventoSanitario.objects.create(
            tipo='Desparasitación', fecha_aplicacion=date(2026, 4, 15),
            estado=True, detalle='Desparasitación de rutina de primavera.',
            veterinario=veterinaria, lote=lotes['IV-2605'],
            cantidad=_dec(n_desparasitados * 5), costo_total=_dec('30000.00'),
            costo_servicio=_dec('15000.00'),
        )
        for animal_id in desparasitados:
            DetalleEvento.objects.create(evento=evento_desparasitacion, animal_id=animal_id, cantidad_dosis=_dec('5'))
        self._crear_movimiento_evento(estancia, evento_desparasitacion)

        # 4. Castración de terneros.
        evento_castracion = EventoSanitario.objects.create(
            tipo='Castración', fecha_aplicacion=date(2026, 8, 5),
            estado=True, detalle='Castración de terneros machos para invernada.',
            veterinario=veterinaria, costo_total=_dec('8000.00'),
            costo_servicio=_dec('4000.00'),
        )
        for nombre in ('Tero', 'Coco'):
            DetalleEvento.objects.create(evento=evento_castracion, animal=animales[nombre])
        self._crear_movimiento_evento(estancia, evento_castracion)

        # 5. Antibiótico para la vaca enferma (Estrella).
        evento_antibiotico = EventoSanitario.objects.create(
            tipo='Antibiótico', fecha_aplicacion=date(2026, 7, 30),
            estado=True, detalle='Tratamiento de pie podrido en Estrella.',
            veterinario=veterinaria, lote=lotes['OX-2604'],
            cantidad=_dec('40.00'), costo_total=_dec('35000.00'),
            costo_servicio=_dec('10000.00'),
        )
        DetalleEvento.objects.create(
            evento=evento_antibiotico, animal=animales['Estrella'], cantidad_dosis=_dec('40.00'),
        )
        self._crear_movimiento_evento(estancia, evento_antibiotico)

        # 6. Inseminación artificial a corral.
        hembras_inseminar = [
            animales['Luna'], animales['Canela'], animales['Flora'],
        ]
        evento_inseminacion = EventoSanitario.objects.create(
            tipo='Inseminación', fecha_aplicacion=date(2026, 2, 5),
            estado=True, detalle='Inseminación artificial a corral de febrero.',
            veterinario=veterinaria, padre=animales['don_julio'],
            padre_donante='Semen Braford - Don Julio (toro probado)',
            costo_total=_dec('120000.00'),
            costo_servicio=_dec('50000.00'),
        )
        for animal in hembras_inseminar:
            DetalleEvento.objects.create(evento=evento_inseminacion, animal=animal)
        self._crear_movimiento_evento(estancia, evento_inseminacion)
        return evento_inseminacion

    def _crear_movimiento_evento(self, estancia, evento):
        if not (evento.estado and (evento.costo_total or _dec('0')) > 0):
            return
        detalle = evento.detalle or f'Gasto de {evento.tipo}.'
        servicio = evento.costo_servicio or _dec('0')
        if servicio > 0:
            detalle = f'{detalle}\nServicio del veterinario: $ {servicio:,.2f}'
        movimiento = MovimientoFinanciero.objects.create(
            tipo='Egreso', nombre=f'Evento sanitario #{evento.id}',
            monto_total=evento.costo_total, fecha=evento.fecha_aplicacion,
            detalle=detalle,
            establecimiento=estancia,
        )
        evento.mov_financiero = movimiento
        evento.save(update_fields=['mov_financiero'])

    # ------------------------------------------------------------------
    # Preñeces y partos
    # ------------------------------------------------------------------
    def _crear_prenieces(self, evento_inseminacion, animales):
        # Preñadas por la inseminación de febrero.
        for nombre in ('Luna', 'Canela', 'Flora'):
            Preniez.objects.create(
                fecha=date(2026, 2, 5), tipo='Inseminación',
                estado_actual='Preñada', madre=animales[nombre],
                padre=animales['don_julio'],
                padre_donante='Semen Braford - Don Julio (toro probado)',
                detalle=f'Preñada registrada desde la inseminación #{evento_inseminacion.id}.',
                evento_sanitario=evento_inseminacion,
            )
        # Preñez natural de Dulce: parto estimado dentro de los próximos 30 días.
        Preniez.objects.create(
            fecha=date(2025, 12, 10), tipo='Natural', estado_actual='Preñada',
            madre=animales['Dulce'], padre=animales['changüi'],
        )
        Preniez.objects.create(
            fecha=date(2026, 4, 18), tipo='Natural', estado_actual='Preñada',
            madre=animales['Nina'], padre=animales['changüi'],
        )
        Preniez.objects.create(
            fecha=date(2026, 8, 2), tipo='Natural', estado_actual='A confirmar',
            madre=animales['Lucía'],
        )
        Preniez.objects.create(
            fecha=date(2026, 8, 2), tipo='Natural', estado_actual='Vacía',
            madre=animales['Aurora'],
        )
        # Preñez finalizada con parto y cría registrada.
        parto = Parto.objects.create(fecha=date(2026, 7, 15), vivo=True)
        Preniez.objects.create(
            fecha=date(2025, 10, 15), tipo='Natural', estado_actual='Preñada',
            madre=animales['Violeta'], padre=animales['changüi'],
            parto=parto,
        )
        self._crear_animal(
            '1200100309', 'Linda', 'Bovino', 'Hembra', 'Braford', 'Colorado',
            date(2026, 7, 15), 75, animales['Violeta'].parcela,
            animales['Violeta'].establecimiento,
            madre=animales['Violeta'], padre=animales['changüi'], parto=parto,
        )

    # ------------------------------------------------------------------
    # Liquidaciones de sueldo
    # ------------------------------------------------------------------
    def _crear_liquidaciones(self, estancia, usuario_operario):
        for fecha in (date(2026, 6, 30), date(2026, 7, 31)):
            liquidacion = LiquidacionSueldo.objects.create(
                fecha=fecha, sueldo=_dec('520000.00'),
                descripcion='Liquidación mensual de sueldo.',
                empleado=usuario_operario, establecimiento=estancia,
            )
            nombre_empleado = f'{usuario_operario.persona.nombre} {usuario_operario.persona.apellido or ""}'.strip()
            movimiento = MovimientoFinanciero.objects.create(
                tipo='Egreso', nombre=f'Sueldo - {nombre_empleado}',
                monto_total=liquidacion.sueldo, fecha=fecha,
                detalle=liquidacion.descripcion, establecimiento=estancia,
            )
            liquidacion.movimiento_financiero = movimiento
            liquidacion.save(update_fields=['movimiento_financiero'])

    # ------------------------------------------------------------------
    # Sanidad (enfermedades y diagnósticos)
    # ------------------------------------------------------------------
    def _crear_sanidad(self, animales):
        enfermedad, _ = Enfermedad.objects.get_or_create(
            nombre='Pododermatitis (Pie podrido)',
            defaults={
                'es_zoonotica': False,
                'descripcion': 'Infección de la pezuña que afecta el aplomo del animal.',
            },
        )
        Diagnostico.objects.create(
            animal=animales['Estrella'], enfermedad=enfermedad,
            fecha_deteccion=date(2026, 7, 28),
            estado_actual='En tratamiento',
            observaciones='Aplicar antibiótico local y mantener en corral seco.',
        )

    # ------------------------------------------------------------------
    # Resumen
    # ------------------------------------------------------------------
    def _resumen(self, estancia, usuario_propietario, usuario_operario):
        conteos = {
            'Animales': Animal.objects.count(),
            'Parcelas': Parcela.objects.filter(establecimiento=estancia).count(),
            'Preñeces': Preniez.objects.count(),
            'Partos': Parto.objects.count(),
            'Ventas': Venta.objects.count(),
            'Compras': Compra.objects.count(),
            'Liquidaciones': LiquidacionSueldo.objects.count(),
            'Movimientos financieros': MovimientoFinanciero.objects.count(),
            'Eventos sanitarios': EventoSanitario.objects.count(),
            'Insumos': Insumo.objects.count(),
            'Lotes': Lote.objects.filter(establecimiento=estancia).count(),
            'Personas': Persona.objects.count(),
            'Usuarios': Usuario.objects.count(),
        }
        self.stdout.write('-' * 70)
        self.stdout.write(self.style.SUCCESS(f'Dataset cargado en "{estancia.nombre}" ({estancia.ubicacion}):'))
        for nombre, cantidad in conteos.items():
            self.stdout.write(f'  {nombre:<22} {cantidad}')
        self.stdout.write('-' * 70)
        self.stdout.write('Usuarios de acceso:')
        self.stdout.write(f'  Propietario: {usuario_propietario.nombre_usuario} / lautaro123')
        self.stdout.write(f'  Operario:    {usuario_operario.nombre_usuario} / pedro123')
        self.stdout.write('  (el operario deberá cambiar su clave en el primer ingreso)')
        self.stdout.write('-' * 70)
