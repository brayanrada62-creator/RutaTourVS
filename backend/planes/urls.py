from django.urls import path
from .views import PlanView
from .solicitudes import RevisarSolicitudPlanView, SolicitudesPlanView

urlpatterns = [
    path('solicitudes-plan/', SolicitudesPlanView.as_view(), name='solicitudes-plan'),
    path('solicitudes-plan/<int:id>/', RevisarSolicitudPlanView.as_view(), name='revisar-solicitud-plan'),
    path('planes/', PlanView.as_view(), name='planes'),
    path('planes/<int:id>/', PlanView.as_view(), name='plan-detalle'),
]