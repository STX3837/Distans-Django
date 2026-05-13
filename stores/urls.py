from django.urls import path

from . import views

urlpatterns = [
    # Público
    path('tiendas/', views.store_list, name='store_list'),
    
    # Admin
    path('gestion/tiendas/', views.store_list_admin, name='store_list_admin'),
    path('gestion/tiendas/nueva/', views.store_create_admin, name='store_create_admin'),
    path('gestion/tiendas/<int:pk>/editar/', views.store_update_admin, name='store_update_admin'),
    path('gestion/tiendas/<int:pk>/eliminar/', views.store_delete_admin, name='store_delete_admin'),
]
