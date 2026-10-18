from django.contrib import admin

# Register your models here.

#roles/admin.py
from django.contrib import admin
from .models import Rol

admin.site.register(Rol)

#usuarios/admin.py
from django.contrib import admin
from .models import Usuario, RecuperarContrasena

admin.site.register(Usuario)
admin.site.register(RecuperarContrasena) 
