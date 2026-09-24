from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reservas', '0002_alter_asientoreserva_id_alter_reserva_id'),
        ('paquetes', '0003_android'),
        ('usuarios', '0002_alter_agencia_id_alter_rol_id_alter_usuario_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='viaje',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='paquetes.viaje'),
        ),
        migrations.AddField(
            model_name='reserva',
            name='estado',
            field=models.CharField(default='pendiente', max_length=20),
        ),
        migrations.AddField(
            model_name='reserva',
            name='abordado',
            field=models.CharField(default='PENDIENTE', max_length=20),
        ),
        migrations.CreateModel(
            name='GpsPunto',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lat', models.DecimalField(decimal_places=6, default=0, max_digits=10)),
                ('lng', models.DecimalField(decimal_places=6, default=0, max_digits=10)),
                ('velocidad', models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('viaje', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='paquetes.viaje')),
            ],
            options={'db_table': 'gps_puntos'},
        ),
        migrations.CreateModel(
            name='Novedad',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(default='novedad', max_length=80)),
                ('detalle', models.CharField(default='', max_length=400)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('viaje', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='paquetes.viaje')),
            ],
            options={'db_table': 'novedades'},
        ),
        migrations.CreateModel(
            name='ChatMensaje',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto', models.CharField(default='', max_length=400)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='usuarios.usuario')),
                ('viaje', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='paquetes.viaje')),
            ],
            options={'db_table': 'chat_mensajes'},
        ),
        migrations.CreateModel(
            name='ParadaViaje',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150)),
                ('orden', models.IntegerField(default=1)),
                ('cumplida', models.BooleanField(default=False)),
                ('viaje', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='paquetes.viaje')),
            ],
            options={'db_table': 'paradas_viaje'},
        ),
    ]
