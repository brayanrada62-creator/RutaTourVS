# SOLO DESARROLLO: base local, nunca Aiven.
from config.settings import *
DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql", "NAME": "rutatour_dev", "USER": "dev", "PASSWORD": "dev",
    "HOST": "127.0.0.1", "PORT": "3306", "TEST": {"NAME": "test_rutatour_dev"},
}}
# La migración destinos/0003 asume una tabla previa que no existe en una base nueva.
MIGRATION_MODULES = {"destinos": "dev_mig.destinos"}
