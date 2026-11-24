from django.urls import path
from .views import ContactoLandingView, PlanView

urlpatterns = [
    path('planes/', PlanView.as_view(), name='planes'),
    path('planes/<int:id>/', PlanView.as_view(), name='plan-detalle'),
    path('contacto/', ContactoLandingView.as_view(), name='contacto-landing'),
]