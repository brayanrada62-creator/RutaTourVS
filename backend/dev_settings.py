"""Configuración solo para desarrollo y pruebas locales. NUNCA toca la base de Aiven.

Sin un .env, config/settings.py apunta a la base de producción. Con este archivo todo va a SQLite:

    python manage.py test --settings=dev_settings
    python manage.py migrate --run-syncdb --settings=dev_settings
    python manage.py runserver --settings=dev_settings

Las tablas se crean desde los modelos porque las migraciones de 'destinos' no corren en SQLite.
Por eso estas 4 pruebas fallan aquí y solo se pueden comprobar con MySQL:
  - MigracionDuplicadosTest y MigracionContrasenasTest: necesitan las migraciones reales.
  - ConcurrenciaTest (2 pruebas): SQLite bloquea la tabla ("database table is locked").
InicioSimultaneoTest también depende de la concurrencia: en SQLite a veces pasa y a veces no.
"""
from django.contrib.auth.hashers import PBKDF2PasswordHasher

from config.settings import *  # noqa: F401,F403
from config.settings import BASE_DIR


class HasherRapido(PBKDF2PasswordHasher):
    """El mismo formato pbkdf2_sha256 con 1 iteración: las pruebas pasan de varios minutos a segundos."""
    iterations = 1


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # ignorado por git
    }
}

MIGRATION_MODULES = {app: None for app in ('usuarios', 'paquetes', 'reservas', 'pagos', 'buses', 'destinos')}

PASSWORD_HASHERS = ['dev_settings.HasherRapido']
