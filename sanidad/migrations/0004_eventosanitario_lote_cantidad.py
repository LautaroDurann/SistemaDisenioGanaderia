from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sanidad', '0003_eventosanitario_castracion'),
        ('inventario', '0004_remove_composiciondieta_cantidad_por_porcion_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventosanitario',
            name='cantidad',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='eventosanitario',
            name='lote',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventario.lote'),
        ),
    ]
