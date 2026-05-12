from django.urls import path

from . import views

urlpatterns = [
    path('accounts/signup/', views.signup, name='signup'),
    path('cuenta/', views.account_detail, name='account_detail'),
    path('gestion/usuarios/', views.admin_user_list, name='admin_user_list'),
    path('gestion/usuarios/nuevo/', views.admin_user_create, name='admin_user_create'),
    path('gestion/usuarios/<int:pk>/editar/', views.admin_user_update, name='admin_user_update'),
    path('gestion/usuarios/<int:pk>/eliminar/', views.admin_user_delete, name='admin_user_delete'),
]