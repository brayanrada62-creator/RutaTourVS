from django.db import migrations, models


def crear_numero_inicial(apps, schema_editor):
    ContactoLanding = apps.get_model('planes', 'ContactoLanding')
    if not ContactoLanding.objects.exists():
        ContactoLanding.objects.create(whatsapp='3022726350')


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0004_precioplan'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContactoLanding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('whatsapp', models.CharField(max_length=10)),
            ],
        ),
        migrations.RunPython(crear_numero_inicial, migrations.RunPython.noop),
    ]
