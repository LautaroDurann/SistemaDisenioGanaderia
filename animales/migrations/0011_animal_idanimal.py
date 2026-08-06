from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animales', '0010_preniez_evento_sanitario'),
    ]

    operations = [
        # El atributo interno "id" pasa a llamarse "idAnimal" manteniendo la
        # columna "id" en la base, para no tocar datos ni relaciones (FK).
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name='animal',
                    old_name='id',
                    new_name='idAnimal',
                ),
                migrations.AlterField(
                    model_name='animal',
                    name='idAnimal',
                    field=models.BigAutoField(db_column='id', primary_key=True, serialize=False, verbose_name='ID'),
                ),
            ],
            database_operations=[],
        ),
    ]
