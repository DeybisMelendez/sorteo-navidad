from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('ranking/', views.leaderboard, name='leaderboard'),
    path('premios/', views.prizes, name='prizes'),
    path('participante/<int:participant_id>/', views.participant_detail, name='participant_detail'),
    # Sesión de los usuarios que ingresan datos.
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='login.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Ingreso de datos (cualquier usuario registrado).
    path('agregar-participante/', views.add_participant, name='add_participant'),
    path('anotar-puntos/', views.add_points, name='add_points'),
    path('eliminar-puntos/<int:entry_id>/', views.delete_point_entry, name='delete_point_entry'),
    # Administración de premios (solo staff).
    path('premios/<int:position>/editar/', views.edit_prize, name='edit_prize'),
    path('premios/asignar-top-5/', views.assign_top_prizes, name='assign_top_prizes'),
    path('premios/<int:prize_id>/reclamar/', views.claim_prize, name='claim_prize'),
]
