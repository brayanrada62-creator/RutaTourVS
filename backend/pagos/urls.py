from django.urls import path
from .views import (
    PagoView, PagoIdView, PagoPrecioView, PagoReferenciaView,
)

urlpatterns = [
    path('pago/', PagoView.as_view(), name='pago'),
    path('pago/<int:id>/', PagoIdView.as_view(), name='pago-id'),
    path('pago/precio/<str:precio>/', PagoPrecioView.as_view(), name='pago-precio'),
    path('pago/referencia/<str:referencia>/', PagoReferenciaView.as_view(), name='pago-referencia'),
]