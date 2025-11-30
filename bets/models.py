from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class Perfil(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    xp = models.IntegerField(default=0)
    nivel = models.IntegerField(default=1)
    
    def atualizar_nivel(self):
        # Exemplo de progressão simples; adapte como quiser
        thresholds = [0, 200, 600, 1500, 3000]  # limites de XP para níveis
        novo_nivel = self.nivel
        for i, t in enumerate(thresholds, start=1):
            if self.xp >= t:
                novo_nivel = i
        if novo_nivel != self.nivel:
            self.nivel = novo_nivel
            self.save()

    def __str__(self):
        return f"{self.user.username} (XP: {self.xp})"

class Modalidade(models.Model):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome

class Jogo(models.Model):
    modalidade = models.ForeignKey(Modalidade, on_delete=models.CASCADE)
    time1 = models.CharField(max_length=100)
    time2 = models.CharField(max_length=100)
    data = models.DateTimeField()
    placar_time1 = models.IntegerField(null=True, blank=True)
    placar_time2 = models.IntegerField(null=True, blank=True)
    finalizado = models.BooleanField(default=False)  # marca quando resultado for publicado
    
    # Odds para mercado 1X2
    odd_time1 = models.DecimalField(max_digits=5, decimal_places=2, default=2.00, help_text="Odd para vitória do Time 1")
    odd_empate = models.DecimalField(max_digits=5, decimal_places=2, default=3.00, help_text="Odd para empate")
    odd_time2 = models.DecimalField(max_digits=5, decimal_places=2, default=2.00, help_text="Odd para vitória do Time 2")
    
    # Odd para placar exato (pode ser calculada dinamicamente ou definida)
    odd_placar_exato = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, help_text="Odd para placar exato")

    def __str__(self):
        return f"{self.time1} x {self.time2} — {self.modalidade}"
    
    def calcular_resultado_1x2(self):
        """Retorna o resultado do jogo no formato 1X2"""
        if self.placar_time1 is None or self.placar_time2 is None:
            return None
        if self.placar_time1 > self.placar_time2:
            return '1'  # Vitória do time 1
        elif self.placar_time1 < self.placar_time2:
            return '2'  # Vitória do time 2
        else:
            return 'X'  # Empate

class TipoAposta(models.TextChoices):
    RESULTADO_1X2 = '1X2', 'Resultado 1X2'
    PLACAR_EXATO = 'PLACAR', 'Placar Exato'
    VENCEDOR = 'VENCEDOR', 'Vencedor'

class Aposta(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='apostas')
    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE, related_name='apostas')
    tipo = models.CharField(max_length=20, choices=TipoAposta.choices, default=TipoAposta.PLACAR_EXATO)
    
    # Para mercado 1X2
    aposta_1x2 = models.CharField(max_length=1, null=True, blank=True, help_text="1, X ou 2")
    
    # Para placar exato
    palpite_time1 = models.IntegerField(null=True, blank=True)
    palpite_time2 = models.IntegerField(null=True, blank=True)
    
    # Valores da aposta
    valor_apostado = models.DecimalField(max_digits=10, decimal_places=2)
    odd_aposta = models.DecimalField(max_digits=5, decimal_places=2)
    ganho_potencial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status da aposta
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('GANHOU', 'Ganhou'),
        ('PERDEU', 'Perdeu'),
        ('CANCELADA', 'Cancelada'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDENTE')
    ganho_realizado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-criado_em']
    
    def calcular_ganho_potencial(self):
        """Calcula o ganho potencial baseado no valor apostado e odd"""
        self.ganho_potencial = self.valor_apostado * self.odd_aposta
        return self.ganho_potencial
    
    def verificar_resultado(self):
        """Verifica se a aposta ganhou ou perdeu"""
        if self.jogo.finalizado and self.jogo.placar_time1 is not None and self.jogo.placar_time2 is not None:
            if self.tipo == TipoAposta.RESULTADO_1X2:
                resultado_jogo = self.jogo.calcular_resultado_1x2()
                if resultado_jogo == self.aposta_1x2:
                    self.status = 'GANHOU'
                    self.ganho_realizado = self.ganho_potencial
                else:
                    self.status = 'PERDEU'
                    self.ganho_realizado = 0
            elif self.tipo == TipoAposta.PLACAR_EXATO:
                if (self.palpite_time1 == self.jogo.placar_time1 and 
                    self.palpite_time2 == self.jogo.placar_time2):
                    self.status = 'GANHOU'
                    self.ganho_realizado = self.ganho_potencial
                else:
                    self.status = 'PERDEU'
                    self.ganho_realizado = 0
            self.save()
            return self.status
    
    def __str__(self):
        if self.tipo == TipoAposta.RESULTADO_1X2:
            return f"{self.usuario.username} - {self.jogo}: {self.aposta_1x2} (R$ {self.valor_apostado})"
        else:
            return f"{self.usuario.username} - {self.jogo}: {self.palpite_time1}x{self.palpite_time2} (R$ {self.valor_apostado})"

# Mantendo o modelo Palpite antigo para compatibilidade (pode ser removido depois)
class Palpite(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE, related_name='palpites')
    palpite_time1 = models.IntegerField()
    palpite_time2 = models.IntegerField()
    pontos = models.IntegerField(default=0)  # pontos ganhados por esse palpite
    criado_em = models.DateTimeField(auto_now_add=True)
    calculado = models.BooleanField(default=False)  # evita recalcular

    class Meta:
        unique_together = ('usuario', 'jogo')  # opcional: apenas 1 palpite por usuário por jogo

    def __str__(self):
        return f"{self.usuario.username} → {self.jogo}: {self.palpite_time1}-{self.palpite_time2}"
