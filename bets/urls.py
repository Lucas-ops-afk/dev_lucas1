from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('ranking/', views.ranking_view, name='ranking'),
    path('jogos/', views.listar_jogos, name='listar_jogos'),
    path('jogos/modalidade/<int:modalidade_id>/', views.listar_jogos, name='jogos_por_modalidade'),
    path('jogos/<int:jogo_id>/palpitar/', views.criar_palpite, name='criar_palpite'),
    path('jogos/<int:jogo_id>/apostar/', views.apostar, name='apostar'),
    path('meus-palpites/', views.meus_palpites, name='meus_palpites'),
    path('minhas-apostas/', views.minhas_apostas, name='minhas_apostas'),
]
