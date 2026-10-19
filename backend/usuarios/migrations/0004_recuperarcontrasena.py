from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_alter_agencia_id_alter_rol_id_alter_usuario_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecuperarContrasena',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(max_length=64, unique=True)),
                ('codigo_hash', models.CharField(max_length=64)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('usado', models.BooleanField(default=False)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='usuarios.usuario')),
            ],
            options={
                'db_table': 'recuperar_contrasena',
            },
        ),
    ]
