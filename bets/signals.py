from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Palpite, Jogo, Perfil, Aposta
from django.db.models import Sum

def calcular_pontos(palpite):
    jogo = palpite.jogo

    # Se o jogo ainda não tem placar final, não calcular
    if jogo.placar_time1 is None or jogo.placar_time2 is None:
        return 0

    # Placar exato: 50 pontos
    if palpite.palpite_time1 == jogo.placar_time1 and palpite.palpite_time2 == jogo.placar_time2:
        return 50

    # Acertou o vencedor ou empate: 10 pontos
    palpite_res = palpite.palpite_time1 - palpite.palpite_time2
    jogo_res = jogo.placar_time1 - jogo.placar_time2

    if (palpite_res > 0 and jogo_res > 0) or \
       (palpite_res < 0 and jogo_res < 0) or \
       (palpite_res == 0 and jogo_res == 0):
        return 10

    return 0


def atualizar_xp_usuario(usuario):
    """Atualiza o XP do usuário somando todos os pontos dos palpites"""
    total_pontos = Palpite.objects.filter(usuario=usuario).aggregate(
        total=Sum('pontos')
    )['total'] or 0

    perfil, created = Perfil.objects.get_or_create(user=usuario)
    if perfil.xp != total_pontos:
        perfil.xp = total_pontos
        perfil.atualizar_nivel()
        perfil.save()


@receiver(post_save, sender=User)
def criar_perfil_usuario(sender, instance, created, **kwargs):
    """Cria automaticamente um Perfil quando um novo usuário é criado"""
    if created:
        Perfil.objects.get_or_create(user=instance)


@receiver(post_save, sender=Jogo)
def atualizar_pontuacoes(sender, instance, **kwargs):
    """Cada vez que um jogo é atualizado, recalcula pontos de todos os palpites e processa apostas."""
    if instance.placar_time1 is None or instance.placar_time2 is None:
        return  # Jogo ainda não terminou

    # Processar palpites antigos (sistema antigo)
    palpites = Palpite.objects.filter(jogo=instance)
    usuarios_afetados = set()

    for palpite in palpites:
        novo_valor = calcular_pontos(palpite)
        if palpite.pontos != novo_valor:
            palpite.pontos = novo_valor
            palpite.calculado = True
            palpite.save(update_fields=['pontos', 'calculado'])
            usuarios_afetados.add(palpite.usuario)

    # Processar apostas (sistema tipo Bet365)
    apostas = Aposta.objects.filter(jogo=instance, status='PENDENTE')
    for aposta in apostas:
        aposta.verificar_resultado()
        
        # Se ganhou, adiciona XP
        if aposta.status == 'GANHOU':
            atualizar_xp_usuario(aposta.usuario)

    # Atualiza XP de todos os usuários que tiveram palpites neste jogo
    for usuario in usuarios_afetados:
        atualizar_xp_usuario(usuario)


@receiver(post_save, sender=Palpite)
def atualizar_xp_ao_criar_palpite(sender, instance, created, **kwargs):
    """Atualiza XP quando um novo palpite é criado"""
    if created:
        atualizar_xp_usuario(instance.usuario)
