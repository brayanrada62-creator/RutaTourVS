from django.urls import path
from .views import ContactoLandingView, PlanView, SolicitudPlanResolverView, SolicitudPlanView

urlpatterns = [
    path('planes/', PlanView.as_view(), name='planes'),
    path('planes/<int:id>/', PlanView.as_view(), name='plan-detalle'),
    path('contacto/', ContactoLandingView.as_view(), name='contacto-landing'),
    path('solicitudes-plan/', SolicitudPlanView.as_view(), name='solicitudes-plan'),
    path('solicitudes-plan/<int:id>/<str:accion>/', SolicitudPlanResolverView.as_view(), name='solicitud-plan-resolver'),
]