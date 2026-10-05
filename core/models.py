from django.db import models
from decimal import Decimal
from django.utils import timezone 
from django.contrib.auth.models import User

# ====================== AGENTE (UNIFICADO) ======================
class Agente(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=15)
    data_contratacao = models.DateField(auto_now_add=True)
    ativo = models.BooleanField(default=True)
    meta_diaria = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.nome

# ====================== CLIENTE ======================
class Cliente(models.Model):
    PACOTE_CHOICES = [
        ('INICIANTE', 'Iniciante'),
        ('EVOLUCAO', 'Evolução'),
        ('PREMIUM', 'Premium'),
    ]

    ESTADO_CIVIL_CHOICES = [
        ('SOLTEIRO', 'Solteiro(a)'),
        ('CASADO', 'Casado(a)'),
        ('UNIAO_ESTAVEL', 'União Estável'),
        ('DIVORCIADO', 'Divorciado(a)'),
        ('VIUVO', 'Viúvo(a)'),
    ]

    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=15)
    bi = models.CharField(max_length=20, blank=True, null=True, verbose_name="Nº de BI")
    agente = models.ForeignKey('Agente', on_delete=models.SET_NULL, null=True, blank=True, related_name='clientes')
    pacote = models.CharField(max_length=20, choices=PACOTE_CHOICES, default='INICIANTE')
    produto_escolhido = models.CharField(max_length=100)
    valor_produto = models.DecimalField(max_digits=10, decimal_places=2)
    data_registo = models.DateTimeField(auto_now_add=True)
    data_previsao_entrega = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    saldo_devedor = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    status = models.CharField(max_length=20, choices=[('ativo', 'Ativo'), ('quitado', 'Quitado')], default='ativo')

    # NOVOS CAMPOS
    data_nascimento = models.DateField(null=True, blank=True, verbose_name="Data de Nascimento")
    estado_civil = models.CharField(max_length=20, choices=ESTADO_CIVIL_CHOICES, blank=True, null=True, verbose_name="Estado Civil")
    numero_filhos = models.PositiveIntegerField(default=0, verbose_name="Número de Filhos")
    profissao = models.CharField(max_length=100, blank=True, null=True, verbose_name="Profissão")
    tipo_negocio = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo de Negócio")
    endereco = models.TextField(blank=True, null=True, verbose_name="Endereço Completo")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações Gerais")

    def __str__(self):
        return self.nome

    def calcular_saldo(self):
        from decimal import Decimal
        from django.db import models
        total_pago = self.pagamentos.filter(confirmado=True).aggregate(
            total=models.Sum('valor')
        )['total'] or Decimal('0')
        self.saldo_devedor = self.valor_produto - total_pago
        if self.saldo_devedor <= 0:
            self.status = 'quitado'
            self.saldo_devedor = 0
        else:
            self.status = 'ativo'
        self.save(update_fields=['saldo_devedor', 'status'])
        return self.saldo_devedor

    def total_pago(self):
        from decimal import Decimal
        from django.db import models
        total = self.pagamentos.filter(confirmado=True).aggregate(
            total=models.Sum('valor')
        )['total'] or Decimal('0')
        return total

    def get_deposito_diario_esperado(self):
        from decimal import Decimal
        if self.pacote == 'INICIANTE':
            return Decimal('100.00')
        elif self.pacote == 'EVOLUCAO':
            return Decimal('200.00')
        elif self.pacote == 'PREMIUM':
            return Decimal('300.00')
        return Decimal('100.00')

    # ========== MÉTODOS DE PREVISÃO (NECESSÁRIOS PARA CHINA MALL) ==========
    def get_dias_restantes(self):
        from decimal import Decimal
        saldo = self.saldo_devedor
        deposito_diario = self.get_deposito_diario_esperado()
        if deposito_diario <= 0:
            return 0
        saldo_dec = Decimal(str(saldo))
        deposito_dec = Decimal(str(deposito_diario))
        dias = saldo_dec / deposito_dec
        return int(dias.to_integral_value(rounding='ROUND_CEILING'))

    def get_semanas_restantes(self):
        from decimal import Decimal
        dias = self.get_dias_restantes()
        if dias <= 0:
            return 0
        dias_dec = Decimal(str(dias))
        semanas = dias_dec / Decimal('7')
        return int(semanas.to_integral_value(rounding='ROUND_CEILING'))

    def get_meses_restantes(self):
        from decimal import Decimal
        dias = self.get_dias_restantes()
        if dias <= 0:
            return 0
        dias_dec = Decimal(str(dias))
        meses = dias_dec / Decimal('30')
        return int(meses.to_integral_value(rounding='ROUND_CEILING'))
    
# ====================== PAGAMENTO ======================
class Pagamento(models.Model):
    METODO_CHOICES = [
        ('cash', 'Dinheiro'),
        ('bancaria', 'Transferência Bancária'),
        ('emola', 'Emola'),
        ('mpesa', 'M-Pesa'),
        ('cheque', 'Cheque'),
        ('outro', 'Outro'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='pagamentos')
    data_pagamento = models.DateField(auto_now_add=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    confirmado = models.BooleanField(default=False)
    agente = models.ForeignKey(Agente, on_delete=models.PROTECT, null=True, blank=True, related_name='pagamentos')
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES, default='cash')
    referencia = models.CharField(max_length=100, blank=True, verbose_name='Referência / Nº Comprovativo')
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.cliente.nome} - {self.valor} ({self.data_pagamento})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if self.confirmado:
            self.cliente.calcular_saldo()
        elif not is_new and not self.confirmado:
            self.cliente.calcular_saldo()

# ====================== DESPESA ======================
class Despesa(models.Model):
    CATEGORIA_CHOICES = [
        ('fixa', 'Fixa'),
        ('variavel', 'Variável'),
        ('transporte', 'Transporte'),
        ('marketing', 'Marketing'),
        ('outros', 'Outros'),
    ]

    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField(default=timezone.now)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='outros')
    observacao = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.descricao} - {self.valor} ({self.data})"

# ====================== SALÁRIO AGENTE ======================
class SalarioAgente(models.Model):
    agente = models.ForeignKey(Agente, on_delete=models.PROTECT)
    mes = models.IntegerField()  # 1-12
    ano = models.IntegerField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    pago = models.BooleanField(default=False)
    data_pagamento = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.agente.nome} - {self.mes}/{self.ano} - {self.valor}"
    
    def get_dias_restantes(self):
        """Calcula o número de dias restantes para quitar o saldo."""
        saldo = self.saldo_devedor
        deposito_diario = self.get_deposito_diario_esperado()
        if deposito_diario <= 0:
            return 0
        saldo_dec = Decimal(str(saldo))
        deposito_dec = Decimal(str(deposito_diario))
        dias = saldo_dec / deposito_dec
        return int(dias.to_integral_value(rounding='ROUND_CEILING'))

    def get_semanas_restantes(self):
        """Calcula o número de semanas restantes (arredondado para cima)."""
        dias = self.get_dias_restantes()
        if dias <= 0:
            return 0
        dias_dec = Decimal(str(dias))
        semanas = dias_dec / Decimal('7')
        return int(semanas.to_integral_value(rounding='ROUND_CEILING'))

    def get_meses_restantes(self):
        """Calcula o número de meses restantes (arredondado para cima, mês = 30 dias)."""
        dias = self.get_dias_restantes()
        if dias <= 0:
            return 0
        dias_dec = Decimal(str(dias))
        meses = dias_dec / Decimal('30')
        return int(meses.to_integral_value(rounding='ROUND_CEILING'))