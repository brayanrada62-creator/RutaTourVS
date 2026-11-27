from django.db import migrations, models


def campos_solicitud_plan():
    return [
        (
            'periodo',
            models.CharField(
                choices=[('mensual', 'Mensual'), ('trimestral', 'Trimestral'), ('anual', 'Anual')],
                default='mensual',
                max_length=20,
            ),
        ),
        ('precio', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
        ('comprobante', models.ImageField(blank=True, default='', max_length=255, upload_to='membresias/')),
        ('motivo', models.CharField(blank=True, default='', max_length=255)),
        ('inicia_el', models.DateField(blank=True, null=True)),
        ('vencimiento', models.DateField(blank=True, null=True)),
    ]


def agregar_campos_faltantes(apps, schema_editor):
    SolicitudPlan = apps.get_model('planes', 'SolicitudPlan')
    with schema_editor.connection.cursor() as cursor:
        columnas = {
            columna.name
            for columna in schema_editor.connection.introspection.get_table_description(
                cursor, SolicitudPlan._meta.db_table
            )
        }

    for nombre, campo in campos_solicitud_plan():
        campo.set_attributes_from_name(nombre)
        campo.model = SolicitudPlan
        if campo.column not in columnas:
            schema_editor.add_field(SolicitudPlan, campo)
            columnas.add(campo.column)


class Migration(migrations.Migration):

    dependencies = [
        ('planes', '0005_contactolanding'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(agregar_campos_faltantes, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='solicitudplan',
                    name=nombre,
                    field=campo,
                )
                for nombre, campo in campos_solicitud_plan()
            ],
        ),
    ]
