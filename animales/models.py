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

    # Identificador interno e incremental. Se usa para referenciar al animal
    # dentro del sistema porque la caravana (id_senasa) puede cambiar.
    # La columna en la base se mantiene como "id" para no alterar los datos
    # ni las relaciones existentes.
    idAnimal = models.BigAutoField(db_column='id', primary_key=True, serialize=False, verbose_name='ID')

    # Caravana SENASA. Admite letras y números, sin símbolos.
    # La unicidad se aplica solo entre animales activos (baja lógica mediante 'activo').
    id_senasa = models.CharField(max_length=50, null=True, blank=True)
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
    # Fecha en la que el animal murió (solo cuando vivo = False).
    fecha_muerte = models.DateField(null=True, blank=True)
    
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

    # Establecimiento al que pertenece el animal (independiente de su parcela).
    # Se mantiene sincronizado al asignar una parcela o al crear/trasladar el animal.
    establecimiento = models.ForeignKey('establecimientos.Establecimiento', on_delete=models.SET_NULL, null=True, blank=True, related_name='animales')
    
    # Relación a sí mismo (idMadre)
    madre = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='hijos')
    padre = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='crias_padre')
    
    compra = models.ForeignKey('finanzas.Compra', on_delete=models.SET_NULL, null=True, blank=True)
    venta = models.ForeignKey('finanzas.Venta', on_delete=models.SET_NULL, null=True, blank=True)
    parto = models.ForeignKey('animales.Parto', on_delete=models.SET_NULL, null=True, blank=True, related_name='crias')

    # Baja lógica: activo=False oculta al animal del sistema pero conserva su historia.
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['id_senasa'],
                condition=models.Q(activo=True),
                name='animal_id_senasa_activo_uniq',
            ),
        ]

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
    estado_actual = models.CharField(max_length=20, choices=ESTADO_CHOICES)

    # Características del padre donante de semen en caso de inseminación.
    padre_donante = models.CharField(max_length=255, blank=True, null=True)

    # --- RELACIONES ---
    madre = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='prenieces_madre')
    padre = models.ForeignKey(Animal, on_delete=models.SET_NULL, null=True, blank=True, related_name='prenieces_padre')
    parto = models.OneToOneField(Parto, on_delete=models.SET_NULL, null=True, blank=True)
    # El veterinario y el movimiento financiero de la inseminación se manejan
    # en el EventoSanitario (tipo 'Inseminación'). La preñez solo se vincula al
    # evento para saber qué hembras quedaron preñadas en esa inseminación.
    evento_sanitario = models.ForeignKey('sanidad.EventoSanitario', on_delete=models.SET_NULL, null=True, blank=True, related_name='prenieces')

    def __str__(self):
        caravana = self.madre.id_senasa if self.madre and self.madre.id_senasa is not None else 'Sin caravana'
        return f"Preñez {self.id} - Madre SENASA: {caravana}"
