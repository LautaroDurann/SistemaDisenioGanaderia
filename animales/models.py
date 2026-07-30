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
        (0, 'Macho'),
        (1, 'Hembra'),
    ]

    id_senasa = models.IntegerField(unique=True) # Clave Única (CU)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    
    # Pesos (permitimos que queden en blanco porque al nacer no tienen peso de destete)
    peso_al_nacer = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    peso_al_destete = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    peso_actual = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Estados booleanos
    vendido = models.BooleanField(default=False)
    vivo = models.BooleanField(default=True)
    enfermo = models.BooleanField(default=False)
    
    # Enums de Estrategia 3
    tipo_animal = models.CharField(max_length=10, choices=TIPO_CHOICES)
    sexo = models.IntegerField(choices=SEXO_CHOICES) 
    
    raza = models.CharField(max_length=100, blank=True, null=True)
    costo_adquisicion = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    color = models.CharField(max_length=100, blank=True, null=True)
    valor_madre = models.CharField(max_length=100, blank=True, null=True)
    diametro_escrotal = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # --- RELACIONES (Claves Foráneas) ---
    # Usamos on_delete=models.SET_NULL para que si borras una parcela, el animal no muera, solo quede "sin parcela"
    parcela = models.ForeignKey('establecimientos.Parcela', on_delete=models.SET_NULL, null=True, blank=True)
    dieta = models.ForeignKey('inventario.Dieta', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Relación a sí mismo (idMadre)
    madre = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='hijos')
    
    compra = models.ForeignKey('finanzas.Compra', on_delete=models.SET_NULL, null=True, blank=True)
    venta = models.ForeignKey('finanzas.Venta', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.nombre} (SENASA: {self.id_senasa})"

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
        return f"Preñez {self.id} - Madre SENASA: {self.madre.id_senasa}"