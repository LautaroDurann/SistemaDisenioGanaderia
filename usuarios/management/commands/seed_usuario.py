import secrets
import string

from datetime import date

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from establecimientos.models import Establecimiento
from usuarios.models import Persona, RolEstablecimiento, Usuario


def _generar_clave_temporal(largo=12):
    alfabeto = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(largo))


class Command(BaseCommand):
    help = (
        'Crea o actualiza el usuario semilla (cuenta raíz) con rol Propietario '
        'y clave temporal que deberá cambiarse en el primer ingreso.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--usuario', default='admin', help='Nombre de usuario de la cuenta raíz.')
        parser.add_argument('--clave', default='', help='Clave temporal. Si se omite, se genera una aleatoria.')
        parser.add_argument('--nombre', default='Administrador', help='Nombre de la persona.')
        parser.add_argument('--apellido', default='', help='Apellido de la persona.')
        parser.add_argument('--email', default='', help='Correo electrónico de la persona.')
        parser.add_argument('--establecimiento-id', type=int, default=None, help='Establecimiento al que se asocia el rol.')

    def handle(self, *args, **options):
        nombre_usuario = options['usuario'].strip()
        clave = options['clave'].strip()
        establecimiento_id = options['establecimiento_id']

        establecimiento = None
        if establecimiento_id is not None:
            establecimiento = Establecimiento.objects.filter(pk=establecimiento_id).first()
            if establecimiento is None:
                self.stderr.write(self.style.ERROR(f'No existe el establecimiento con id {establecimiento_id}.'))
                raise SystemExit(1)
        if establecimiento is None:
            establecimiento = Establecimiento.objects.first()
        if establecimiento is None:
            establecimiento = Establecimiento.objects.create(
                nombre='Establecimiento principal',
                fecha_inicio=date.today(),
                ubicacion='Sin especificar',
            )
            self.stdout.write(self.style.WARNING(f'Se creó el establecimiento: {establecimiento.nombre}'))

        usuario = Usuario.objects.filter(nombre_usuario=nombre_usuario).first()
        if usuario is None:
            persona = Persona.objects.create(
                nombre=options['nombre'].strip() or 'Administrador',
                apellido=options['apellido'].strip() or None,
                correo_electronico=options['email'].strip() or None,
            )
            usuario = Usuario.objects.create(
                nombre_usuario=nombre_usuario,
                clave=make_password(clave or _generar_clave_temporal()),
                persona=persona,
            )
            self.stdout.write(self.style.SUCCESS(f'Usuario creado: {usuario.nombre_usuario}'))
        else:
            self.stdout.write(self.style.WARNING(f'El usuario {usuario.nombre_usuario} ya existía; se actualizó.'))

        clave_temporal = clave or _generar_clave_temporal()
        usuario.clave = make_password(clave_temporal)
        usuario.debe_cambiar_clave = True
        usuario.save(update_fields=['clave', 'debe_cambiar_clave'])

        rol = RolEstablecimiento.objects.filter(usuario=usuario, establecimiento=establecimiento).first()
        if rol is None:
            rol = RolEstablecimiento.objects.create(
                usuario=usuario,
                establecimiento=establecimiento,
                nombre='Propietario',
                fecha_ingreso=date.today(),
                estado_acceso=True,
            )
        else:
            rol.nombre = 'Propietario'
            rol.estado_acceso = True
            rol.save(update_fields=['nombre', 'estado_acceso'])

        self.stdout.write('-' * 60)
        self.stdout.write(self.style.SUCCESS('Cuenta raíz configurada:'))
        self.stdout.write(f'  Usuario:      {usuario.nombre_usuario}')
        self.stdout.write(f'  Clave:        {clave_temporal}')
        self.stdout.write(f'  Rol:          {rol.nombre}')
        self.stdout.write(f'  Establecimiento: {establecimiento.nombre}')
        self.stdout.write('  Nota: se exigirá el cambio de clave en el primer ingreso.')
        self.stdout.write('-' * 60)
