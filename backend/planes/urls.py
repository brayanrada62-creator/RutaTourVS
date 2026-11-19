from django.urls import path
from .views import PlanView

urlpatterns = [
    path('planes/', PlanView.as_view(), name='planes'),
]