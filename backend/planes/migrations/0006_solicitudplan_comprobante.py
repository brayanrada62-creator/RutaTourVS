from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0005_contactolanding'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudplan',
            name='periodo',
            field=models.CharField(
                choices=[('mensual', 'Mensual'), ('trimestral', 'Trimestral'), ('anual', 'Anual')],
                default='mensual',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='solicitudplan',
            name='precio',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='solicitudplan',
            name='comprobante',
            field=models.ImageField(blank=True, default='', max_length=255, upload_to='membresias/'),
        ),
        migrations.AddField(
            model_name='solicitudplan',
            name='motivo',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='solicitudplan',
            name='inicia_el',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='solicitudplan',
            name='vencimiento',
            field=models.DateField(blank=True, null=True),
        ),
    ]
