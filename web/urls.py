from django.urls import path

from inventario.views import insumo_detalle, insumos, insumos_api
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('stock/', views.stock, name='stock'),
    path('finanzas/', views.finanzas, name='finanzas'),
    path('finanzas/ventas/', views.ventas, name='ventas'),
    path('finanzas/compras/', views.compras, name='compras'),
    # Se conserva la URL anterior para enlaces guardados.
    path('movimientos/', views.finanzas, name='movimientos'),
    path('potreros/', views.potreros, name='potreros'),
    path('vacunacion/', views.vacunacion, name='vacunacion'),
    path('pesajes/', views.pesajes, name='pesajes'),
    path('alimentacion/', views.alimentacion, name='alimentacion'),
    path('insumos/', insumos, name='insumos'),
    path('api/insumos/', insumos_api, name='insumos_api'),
    path('api/insumos/<int:insumo_id>/', insumo_detalle, name='insumo_detalle'),
    path('usuarios/', views.usuarios, name='usuarios'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('api/stock/', views.stock_api, name='stock_api'),
    path('api/animales/', views.crear_animal, name='crear_animal'),
    path('api/animales/<int:animal_id>/', views.actualizar_animal, name='actualizar_animal'),
    path('api/animales/<int:animal_id>/eliminar/', views.eliminar_animal, name='eliminar_animal'),
    path('api/pesajes/', views.crear_pesaje, name='crear_pesaje'),
    path('api/movimientos/', views.crear_movimiento, name='crear_movimiento'),
    path('api/finanzas/movimientos/', views.finanzas_api_list_create, name='api_finanzas_movimientos'),
    path('api/finanzas/movimientos/<int:movimiento_id>/', views.actualizar_movimiento_financiero, name='actualizar_movimiento_financiero'),
    path('api/finanzas/movimientos/<int:movimiento_id>/eliminar/', views.eliminar_movimiento_financiero, name='eliminar_movimiento_financiero'),
    path('api/compradores/', views.crear_comprador, name='crear_comprador'),
    path('api/compradores/<int:comprador_id>/', views.actualizar_comprador, name='actualizar_comprador'),
    path('api/compradores/<int:comprador_id>/eliminar/', views.eliminar_comprador, name='eliminar_comprador'),
    path('api/ventas/', views.crear_venta, name='crear_venta'),
    path('api/ventas/<int:venta_id>/', views.actualizar_venta, name='actualizar_venta'),
    path('api/ventas/<int:venta_id>/eliminar/', views.eliminar_venta, name='eliminar_venta'),
    path('api/potreros/', views.crear_potrero, name='crear_potrero'),
    path('api/potreros/<int:parcela_id>/eliminar/', views.eliminar_potrero, name='eliminar_potrero'),
]
