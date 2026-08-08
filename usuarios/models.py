from django.db import models

# 1. Clase Base: Persona
class Persona(models.Model):
    # Django crea el id (idPersona) automáticamente.
    dni = models.CharField(max_length=8, unique=True, null=True, blank=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, null=True, blank=True)
    correo_electronico = models.EmailField(max_length=100, unique=True, null=True, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return ' '.join(parte for parte in (self.nombre, self.apellido) if parte)


class Telefono(models.Model):
    # En Django, usar IntegerField es equivalente a tu INT
    cod_area = models.IntegerField()
    numero = models.IntegerField()
    
    # Clave Foránea (CF): Conecta el teléfono con la persona.
    # on_delete=models.CASCADE significa que si se borra la persona, se borran sus teléfonos.
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name='telefonos')

    def __str__(self):
        return f"{self.cod_area} - {self.numero} ({self.persona.nombre})"

# 2. Clases que heredan de Persona (Estrategia 1 de tu modelo)
# Al heredar de Persona, Django crea automáticamente la tabla y la relación (OneToOne)
class Veterinario(Persona):
    pass # "pass" significa que no agregamos campos nuevos por ahora, solo hereda.

class Proveedor(Persona):
    pass

class Comprador(Persona):
    pass

# 3. Usuario
class Usuario(models.Model):
    nombre_usuario = models.CharField(max_length=100, unique=True)
    clave = models.CharField(max_length=100) # En un proyecto real esto se encripta
    # Si está activo, el usuario debe reemplazar la clave temporal en su próximo ingreso.
    debe_cambiar_clave = models.BooleanField(default=False)
    # Último ingreso al sistema (se actualiza en cada inicio de sesión).
    fecha_ultimo_acceso = models.DateTimeField(null=True, blank=True)
    # Fecha de alta del usuario (se asigna automáticamente al crearlo).
    fecha_creacion = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    # Relación 1 a 1 con Persona (un usuario es una persona)
    persona = models.OneToOneField(Persona, on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre_usuario

# 4. Tabla Intermedia: RolEstablecimiento
class RolEstablecimiento(models.Model):
    ROLES_CHOICES = [
        ('Propietario', 'Propietario'),
        ('Operario', 'Operario'),
    ]
    
    nombre = models.CharField(max_length=50, choices=ROLES_CHOICES)
    descripcion = models.CharField(max_length=100, blank=True, null=True)
    fecha_ingreso = models.DateField()
    estado_acceso = models.BooleanField(default=True)
    
    # Claves Foráneas
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    # Usamos comillas para 'establecimientos.Establecimiento' porque esa clase la vamos a crear después
    establecimiento = models.ForeignKey('establecimientos.Establecimiento', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.nombre} - {self.usuario.nombre_usuario}"