from django.db import models

# 1. Parto (La ponemos primero para que Preñez pueda referenciarla)
class Parto(models.Model):
    fecha = models.DateField()
    vivo = models.BooleanField(default=True)

    def __str__(self):
        return f"Parto {self.id} - {self.fecha}"

# 2. Animal (Estrategia 3 de herencia: Todo en una sola tabla)
class Animal(models.Model):
    TIPO_CHOICES = [
        ('Bovino', 'Bovino'),
        ('Porcino', 'Porcino'),
        ('Ovino', 'Ovino'),
    ]
    SEXO_CHOICES = [
        ('Macho', 'Macho'),
        ('Hembra', 'Hembra'),
    ]

    id_senasa = models.IntegerField(unique=True, null=True, blank=True) # Clave Única (CU)
    nombre = models.CharField(max_length=100, blank=True, default='')
    descripcion = models.TextField(blank=True, null=True)
    foto = models.ImageField(upload_to='animales/', blank=True, null=True)
    
    # Pesos (permitimos que queden en blanco porque al nacer no tienen peso de destete)
    peso_al_nacer = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    peso_al_destete = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    peso_actual = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Estados booleanos
    vendido = models.BooleanField(default=False)
    vivo = models.BooleanField(default=True)
    enfermo = models.BooleanField(default=False)
    # Se actualiza automáticamente al registrar un evento sanitario de castración.
    castrado = models.BooleanField(default=False)
    
    # Enums de Estrategia 3
    tipo_animal = models.CharField(max_length=10, choices=TIPO_CHOICES)
    sexo = models.CharField(max_length=10, choices=SEXO_CHOICES) 
    
    raza = models.CharField(max_length=100, blank=True, null=True)
    costo_adquisicion = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    color = models.CharField(max_length=100, blank=True, null=True)
    #valor_madre = models.CharField(max_length=100, blank=True, null=True)
    diametro_escrotal = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # --- RELACIONES (Claves Foráneas) ---
    # Usamos on_delete=models.SET_NULL para que si borras una parcela, el animal no muera, solo quede "sin parcela"
    parcela = models.ForeignKey('establecimientos.Parcela', on_delete=models.SET_NULL, null=True, blank=True)
    dieta = models.ForeignKey('inventario.Dieta', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Relación a sí mismo (idMadre)
    madre = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='hijos')
    padre = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='crias_padre')
    
    compra = models.ForeignKey('finanzas.Compra', on_delete=models.SET_NULL, null=True, blank=True)
    venta = models.ForeignKey('finanzas.Venta', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        caravana = self.id_senasa if self.id_senasa is not None else 'Sin caravana'
        return f"{self.nombre or 'S/N'} (SENASA: {caravana})"

# 3. Preñez (Evitamos usar la "ñ" en el nombre de la clase por buenas prácticas en programación)
class Preniez(models.Model):
    TIPO_CHOICES = [
        ('Natural', 'Natural'),
        ('Inseminación', 'Inseminación'),
    ]
    ESTADO_CHOICES = [
        ('Preñada', 'Preñada'),
        ('A confirmar', 'A confirmar'),
        ('Vacía', 'Vacía'),
    ]

    fecha = models.DateField()
    detalle = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    costo_inseminacion = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estado_actual = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    
    # --- RELACIONES ---
    madre = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='prenieces_madre')
    padre = models.ForeignKey(Animal, on_delete=models.SET_NULL, null=True, blank=True, related_name='prenieces_padre')
    parto = models.OneToOneField(Parto, on_delete=models.SET_NULL, null=True, blank=True)
    veterinario = models.ForeignKey('usuarios.Veterinario', on_delete=models.SET_NULL, null=True, blank=True)
    mov_financiero = models.ForeignKey('finanzas.MovimientoFinanciero', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        caravana = self.madre.id_senasa if self.madre and self.madre.id_senasa is not None else 'Sin caravana'
        return f"Preñez {self.id} - Madre SENASA: {caravana}"


class Pesaje(models.Model):
    """Registro histórico: el peso_actual del animal es solo una referencia rápida."""
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='pesajes')
    fecha = models.DateField()
    peso = models.DecimalField(max_digits=8, decimal_places=2)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['fecha', 'id']

    def __str__(self):
        caravana = self.animal.id_senasa if self.animal and self.animal.id_senasa is not None else 'Sin caravana'
        return f"Pesaje {caravana}: {self.peso} kg"


class MovimientoAnimal(models.Model):
    TIPO_CHOICES = [
        ('Alta', 'Alta'), ('Traslado', 'Traslado'), ('Venta', 'Venta'),
        ('Baja', 'Baja'), ('Nacimiento', 'Nacimiento'), ('Compra', 'Compra'),
    ]
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='movimientos')
    fecha = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    origen = models.ForeignKey('establecimientos.Parcela', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_origen')
    destino = models.ForeignKey('establecimientos.Parcela', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_destino')
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        caravana = self.animal.id_senasa if self.animal and self.animal.id_senasa is not None else 'Sin caravana'
        return f"{self.tipo} - {caravana} ({self.fecha})"
