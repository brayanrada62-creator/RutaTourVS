from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0011_agencia_activo'),
    ]

    operations = [
        migrations.AddField(
            model_name='agencia',
            name='banco',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='agencia',
            name='tipo_cuenta',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
        migrations.AddField(
            model_name='agencia',
            name='numero_cuenta',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='agencia',
            name='titular',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
    ]
