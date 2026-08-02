from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('stock/', views.stock, name='stock'),
    path('movimientos/', views.movimientos, name='movimientos'),
    path('potreros/', views.potreros, name='potreros'),
    path('vacunacion/', views.vacunacion, name='vacunacion'),
    path('pesajes/', views.pesajes, name='pesajes'),
    path('alimentacion/', views.alimentacion, name='alimentacion'),
    path('usuarios/', views.usuarios, name='usuarios'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('api/stock/', views.stock_api, name='stock_api'),
    path('api/animales/', views.crear_animal, name='crear_animal'),
    path('api/animales/<int:animal_id>/', views.actualizar_animal, name='actualizar_animal'),
    path('api/animales/<int:animal_id>/eliminar/', views.eliminar_animal, name='eliminar_animal'),
    path('api/pesajes/', views.crear_pesaje, name='crear_pesaje'),
    path('api/movimientos/', views.crear_movimiento, name='crear_movimiento'),
    path('api/potreros/', views.crear_potrero, name='crear_potrero'),
    path('api/potreros/<int:parcela_id>/eliminar/', views.eliminar_potrero, name='eliminar_potrero'),
]
