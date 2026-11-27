from django.urls import path
<<<<<<< HEAD
from .views import ContactoLandingView, PlanView, SolicitudPlanResolverView, SolicitudPlanView
=======
from .views import ContactoLandingView, PlanView
from .solicitudes import RevisarSolicitudPlanView, SolicitudesPlanView
>>>>>>> 6cfc482172709f5ac336187ac85d1405e151bf01

urlpatterns = [
    path('solicitudes-plan/', SolicitudesPlanView.as_view(), name='solicitudes-plan'),
    path('solicitudes-plan/<int:id>/', RevisarSolicitudPlanView.as_view(), name='revisar-solicitud-plan'),
    path('planes/', PlanView.as_view(), name='planes'),
    path('planes/<int:id>/', PlanView.as_view(), name='plan-detalle'),
    path('contacto/', ContactoLandingView.as_view(), name='contacto-landing'),
    path('solicitudes-plan/', SolicitudPlanView.as_view(), name='solicitudes-plan'),
    path('solicitudes-plan/<int:id>/<str:accion>/', SolicitudPlanResolverView.as_view(), name='solicitud-plan-resolver'),
]