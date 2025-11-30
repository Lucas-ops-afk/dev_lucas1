from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Perfil, Jogo, Modalidade, Palpite, Aposta, TipoAposta
from django.db.models import Q
from decimal import Decimal

def home(request):
    """Página inicial com informações sobre o sistema"""
    modalidades = Modalidade.objects.all()
    jogos_proximos = Jogo.objects.filter(
        data__gte=timezone.now(),
        finalizado=False
    ).order_by('data')[:5]
    
    context = {
        'modalidades': modalidades,
        'jogos_proximos': jogos_proximos,
    }
    return render(request, 'home.html', context)

def ranking_view(request):
    """Exibe o ranking de jogadores por XP"""
    top = Perfil.objects.select_related('user').order_by('-xp')[:50]
    return render(request, 'ranking.html', {'top': top})

def listar_jogos(request, modalidade_id=None):
    """Lista todos os jogos, opcionalmente filtrados por modalidade"""
    jogos = Jogo.objects.select_related('modalidade').all()
    
    if modalidade_id:
        modalidade = get_object_or_404(Modalidade, id=modalidade_id)
        jogos = jogos.filter(modalidade=modalidade)
    else:
        modalidade = None
    
    # Separar jogos por status
    jogos_futuros = jogos.filter(data__gte=timezone.now(), finalizado=False).order_by('data')
    jogos_passados = jogos.filter(
        Q(data__lt=timezone.now()) | Q(finalizado=True)
    ).order_by('-data')
    
    modalidades = Modalidade.objects.all()
    
    context = {
        'jogos_futuros': jogos_futuros,
        'jogos_passados': jogos_passados,
        'modalidades': modalidades,
        'modalidade_selecionada': modalidade,
    }
    return render(request, 'jogos/listar.html', context)

@login_required
def criar_palpite(request, jogo_id):
    """Permite ao usuário criar um palpite para um jogo"""
    jogo = get_object_or_404(Jogo, id=jogo_id)
    
    # Verificar se o jogo já passou ou está finalizado
    if jogo.finalizado or jogo.data < timezone.now():
        messages.error(request, 'Não é possível palpitar em jogos que já foram finalizados!')
        return redirect('listar_jogos')
    
    # Verificar se já existe palpite
    palpite_existente = Palpite.objects.filter(usuario=request.user, jogo=jogo).first()
    
    if request.method == 'POST':
        palpite_time1 = request.POST.get('palpite_time1')
        palpite_time2 = request.POST.get('palpite_time2')
        
        try:
            palpite_time1 = int(palpite_time1)
            palpite_time2 = int(palpite_time2)
            
            if palpite_time1 < 0 or palpite_time2 < 0:
                messages.error(request, 'Os placares não podem ser negativos!')
            else:
                if palpite_existente:
                    # Atualizar palpite existente
                    palpite_existente.palpite_time1 = palpite_time1
                    palpite_existente.palpite_time2 = palpite_time2
                    palpite_existente.save()
                    messages.success(request, 'Palpite atualizado com sucesso!')
                else:
                    # Criar novo palpite
                    Palpite.objects.create(
                        usuario=request.user,
                        jogo=jogo,
                        palpite_time1=palpite_time1,
                        palpite_time2=palpite_time2
                    )
                    messages.success(request, 'Palpite criado com sucesso!')
                
                return redirect('listar_jogos')
        except ValueError:
            messages.error(request, 'Por favor, insira valores numéricos válidos!')
    
    context = {
        'jogo': jogo,
        'palpite_existente': palpite_existente,
    }
    return render(request, 'jogos/criar_palpite.html', context)

@login_required
def meus_palpites(request):
    """Lista todos os palpites do usuário logado"""
    palpites = Palpite.objects.filter(
        usuario=request.user
    ).select_related('jogo', 'jogo__modalidade').order_by('-criado_em')
    
    # Estatísticas
    total_palpites = palpites.count()
    total_pontos = sum(p.pontos for p in palpites)
    palpites_certos = palpites.filter(pontos__gt=0).count()
    
    # Obter ou criar perfil
    perfil, created = Perfil.objects.get_or_create(user=request.user)
    
    context = {
        'palpites': palpites,
        'total_palpites': total_palpites,
        'total_pontos': total_pontos,
        'palpites_certos': palpites_certos,
        'perfil': perfil,
    }
    return render(request, 'palpites/meus_palpites.html', context)

@login_required
def apostar(request, jogo_id):
    """Sistema tipo Bet365 - Criar aposta com odds e valores"""
    jogo = get_object_or_404(Jogo, id=jogo_id)
    perfil, created = Perfil.objects.get_or_create(user=request.user)
    
    # Verificar se o jogo já passou ou está finalizado
    if jogo.finalizado or jogo.data < timezone.now():
        messages.error(request, 'Não é possível apostar em jogos que já foram finalizados!')
        return redirect('listar_jogos')
    
    if request.method == 'POST':
        tipo_aposta = request.POST.get('tipo_aposta')
        valor_apostado = request.POST.get('valor_apostado')
        
        try:
            valor_apostado = Decimal(valor_apostado)
            
            # Validar valor mínimo
            if valor_apostado < Decimal('1.00'):
                messages.error(request, 'O valor mínimo de aposta é R$ 1,00!')
                return redirect('apostar', jogo_id=jogo.id)
            
            odd_aposta = None
            aposta_1x2 = None
            palpite_time1 = None
            palpite_time2 = None
            
            if tipo_aposta == TipoAposta.RESULTADO_1X2:
                aposta_1x2 = request.POST.get('aposta_1x2')
                if aposta_1x2 == '1':
                    odd_aposta = jogo.odd_time1
                elif aposta_1x2 == 'X':
                    odd_aposta = jogo.odd_empate
                elif aposta_1x2 == '2':
                    odd_aposta = jogo.odd_time2
                else:
                    messages.error(request, 'Selecione uma opção válida!')
                    return redirect('apostar', jogo_id=jogo.id)
            
            elif tipo_aposta == TipoAposta.PLACAR_EXATO:
                palpite_time1 = int(request.POST.get('palpite_time1', 0))
                palpite_time2 = int(request.POST.get('palpite_time2', 0))
                odd_aposta = jogo.odd_placar_exato
                
                if palpite_time1 < 0 or palpite_time2 < 0:
                    messages.error(request, 'Os placares não podem ser negativos!')
                    return redirect('apostar', jogo_id=jogo.id)
            
            # Criar aposta
            aposta = Aposta.objects.create(
                usuario=request.user,
                jogo=jogo,
                tipo=tipo_aposta,
                aposta_1x2=aposta_1x2,
                palpite_time1=palpite_time1,
                palpite_time2=palpite_time2,
                valor_apostado=valor_apostado,
                odd_aposta=odd_aposta,
                status='PENDENTE'
            )
            
            # Calcular ganho potencial
            aposta.calcular_ganho_potencial()
            aposta.save()
            
            messages.success(request, f'Aposta criada com sucesso! Ganho potencial: R$ {aposta.ganho_potencial:.2f}')
            return redirect('minhas_apostas')
            
        except (ValueError, TypeError) as e:
            messages.error(request, 'Por favor, insira valores válidos!')
    
    context = {
        'jogo': jogo,
        'perfil': perfil,
    }
    return render(request, 'apostas/apostar.html', context)

@login_required
def minhas_apostas(request):
    """Lista todas as apostas do usuário (sistema tipo Bet365)"""
    apostas = Aposta.objects.filter(
        usuario=request.user
    ).select_related('jogo', 'jogo__modalidade').order_by('-criado_em')
    
    perfil, created = Perfil.objects.get_or_create(user=request.user)
    
    # Estatísticas
    total_apostas = apostas.count()
    apostas_ganhas = apostas.filter(status='GANHOU').count()
    apostas_perdidas = apostas.filter(status='PERDEU').count()
    apostas_pendentes = apostas.filter(status='PENDENTE').count()
    total_ganho = sum(a.ganho_realizado for a in apostas.filter(status='GANHOU'))
    total_apostado = sum(a.valor_apostado for a in apostas)
    
    context = {
        'apostas': apostas,
        'perfil': perfil,
        'total_apostas': total_apostas,
        'apostas_ganhas': apostas_ganhas,
        'apostas_perdidas': apostas_perdidas,
        'apostas_pendentes': apostas_pendentes,
        'total_ganho': total_ganho,
        'total_apostado': total_apostado,
    }
    return render(request, 'apostas/minhas_apostas.html', context)
