# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db import models
from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
import json
from .utils import enviar_notificacao_whatsapp
from .forms import PagamentoForm
from .models import Cliente, Agente, Pagamento, Despesa, SalarioAgente
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


from django.contrib.auth.decorators import user_passes_test

def admin_required(view_func):
    """Decorador que verifica se o usuário é superusuário, senão redireciona para /clientes/"""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_superuser:
            messages.warning(request, 'Acesso restrito a administradores.')
            return redirect('lista_clientes')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# ====================== PÁGINA INICIAL ======================
def home(request):
    return render(request, 'core/home.html')


# ====================== AGENTES (APENAS ADMIN) ======================
@admin_required
def lista_agentes(request):
    agentes = Agente.objects.all().order_by('nome')
    return render(request, 'core/lista_agentes.html', {'agentes': agentes})

@admin_required
def cadastrar_agente(request):
    if request.method == 'POST':
        nome = request.POST.get('nome')
        telefone = request.POST.get('telefone')
        meta_diaria = request.POST.get('meta_diaria', 0)
        if nome and telefone:
            Agente.objects.create(
                nome=nome,
                telefone=telefone,
                meta_diaria=meta_diaria
            )
            messages.success(request, f'Agente {nome} cadastrado com sucesso!')
            return redirect('lista_agentes')
        else:
            messages.error(request, 'Nome e telefone são obrigatórios.')
    return render(request, 'core/cadastrar_agente.html')


# ====================== CLIENTES (AGENTE PODE VER) ======================
@login_required
def lista_clientes(request):
    # Se for superusuário (admin), mostra todos
    if request.user.is_superuser:
        clientes = Cliente.objects.all().order_by('nome')
        total_clientes = clientes.count()
        total_ativos = Cliente.objects.filter(status='ativo').count()
        total_quitados = Cliente.objects.filter(status='quitado').count()
        # Calcular valor total dos produtos
        valor_total = clientes.aggregate(total=Sum('valor_produto'))['total'] or Decimal('0')
    else:
        # Tenta obter o agente ligado ao utilizador
        try:
            agente = request.user.agente
            clientes = Cliente.objects.filter(agente=agente).order_by('nome')
            total_clientes = clientes.count()
            total_ativos = clientes.filter(status='ativo').count()
            total_quitados = clientes.filter(status='quitado').count()
            valor_total = clientes.aggregate(total=Sum('valor_produto'))['total'] or Decimal('0')
        except Agente.DoesNotExist:
            clientes = Cliente.objects.none()
            total_clientes = 0
            total_ativos = 0
            total_quitados = 0
            valor_total = Decimal('0')
            messages.warning(request, 'Você não está associado a nenhum agente.')
    
    context = {
        'clientes': clientes,
        'total_clientes': total_clientes,
        'total_ativos': total_ativos,
        'total_quitados': total_quitados,
        'valor_total': valor_total,
    }
    return render(request, 'core/lista_clientes.html', context)

@login_required
def cadastrar_cliente(request):
    # === VERIFICA SE O USUÁRIO É UM AGENTE ===
    try:
        agente_logado = request.user.agente
        is_agente = True
    except Agente.DoesNotExist:
        agente_logado = None
        is_agente = False

    # === SE FOR ADMIN, MOSTRA LISTA DE AGENTES PARA ESCOLHER ===
    if request.user.is_superuser:
        agentes_disponiveis = Agente.objects.filter(ativo=True).order_by('nome')
    else:
        agentes_disponiveis = []

    if request.method == 'POST':
        nome = request.POST.get('nome')
        telefone = request.POST.get('telefone')
        bi = request.POST.get('bi', '')
        pacote = request.POST.get('pacote')
        produto_escolhido = request.POST.get('produto_escolhido')
        valor_produto = request.POST.get('valor_produto')
        data_previsao_entrega = request.POST.get('data_previsao_entrega')
        agente_id = request.POST.get('agente')  # só admin preenche

        tipo_negocio = request.POST.get('tipo_negocio', '')
        data_nascimento = request.POST.get('data_nascimento') or None
        estado_civil = request.POST.get('estado_civil', '')
        numero_filhos = request.POST.get('numero_filhos', 0)
        profissao = request.POST.get('profissao', '')
        endereco = request.POST.get('endereco', '')
        observacoes = request.POST.get('observacoes', '')

        if nome and telefone and pacote and produto_escolhido and valor_produto:
            cliente = Cliente(
                nome=nome,
                telefone=telefone,
                bi=bi,
                pacote=pacote,
                produto_escolhido=produto_escolhido,
                valor_produto=valor_produto,
                data_previsao_entrega=data_previsao_entrega or None,
                saldo_devedor=valor_produto,
                status='ativo',
                tipo_negocio=tipo_negocio,
                data_nascimento=data_nascimento,
                estado_civil=estado_civil,
                numero_filhos=numero_filhos,
                profissao=profissao,
                endereco=endereco,
                observacoes=observacoes,
            )

            # === ASSOCIAÇÃO DO AGENTE ===
            if is_agente:
                # Se for agente, força a associação ao agente logado
                cliente.agente = agente_logado
            elif agente_id and request.user.is_superuser:
                # Se for admin e escolheu um agente
                try:
                    agente = Agente.objects.get(id=agente_id)
                    cliente.agente = agente
                except Agente.DoesNotExist:
                    pass

            cliente.save()
            messages.success(request, f'Cliente {nome} cadastrado com sucesso!')
            return redirect('lista_clientes')
        else:
            messages.error(request, 'Preencha todos os campos obrigatórios.')

    pacote_choices = Cliente.PACOTE_CHOICES
    return render(request, 'core/cadastrar_cliente.html', {
        'pacote_choices': pacote_choices,
        'agentes': agentes_disponiveis,
        'is_agente': is_agente,
        'agente_logado': agente_logado,
    })

# ====================== LANÇAR PAGAMENTO (AGENTE PODE) ======================
@login_required
def lancar_pagamento(request):
    try:
        agente = request.user.agente
    except Agente.DoesNotExist:
        # Se for admin, pode ver todos
        agente = None

    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        agente_id = request.POST.get('agente')
        valor = request.POST.get('valor')
        metodo = request.POST.get('metodo')
        referencia = request.POST.get('referencia', '')
        observacao = request.POST.get('observacao', '')

        if not cliente_id or not agente_id or not valor:
            messages.error(request, 'Preencha todos os campos obrigatórios.')
            return redirect('lancar_pagamento')

        try:
            cliente = Cliente.objects.get(id=cliente_id)
            # Se for agente, só pode pagar clientes que lhe pertencem
            if agente and cliente.agente != agente:
                messages.error(request, 'Este cliente não pertence a você.')
                return redirect('lancar_pagamento')

            agente_obj = Agente.objects.get(id=agente_id)
            valor_dec = Decimal(valor)

            if cliente.status == 'quitado':
                messages.warning(request, f'O cliente {cliente.nome} já quitou o produto.')
                return redirect('lancar_pagamento')

            pagamento = Pagamento(
                cliente=cliente,
                valor=valor_dec,
                agente=agente_obj,
                metodo=metodo,
                referencia=referencia,
                observacao=observacao,
                confirmado=True
            )
            pagamento.save()

            # --- ENVIA WHATSAPP ---
            mensagem = f"""💰 *Pagamento registado no Projeto Pouco Pouco!*

Você pagou o valor de {valor_dec} MT
no pacote {cliente.pacote}

📅 Data do pagamento: {pagamento.data_pagamento}
🏬 Loja: CHINA MAL

Continue acompanhando o seu progresso!
"""
            sucesso, resposta = enviar_notificacao_whatsapp(cliente.telefone, mensagem)

            if sucesso:
                messages.success(request, f'Pagamento de {valor_dec} MZN lançado para {cliente.nome} com sucesso! Notificação WhatsApp enviada.')
            else:
                messages.warning(request, f'Pagamento registado, mas falha ao enviar WhatsApp: {resposta}')

            return redirect('dashboard')

        except Cliente.DoesNotExist:
            messages.error(request, 'Cliente não encontrado.')
        except Agente.DoesNotExist:
            messages.error(request, 'Agente não encontrado.')
        except Exception as e:
            messages.error(request, f'Erro: {str(e)}')

        return redirect('lancar_pagamento')

    # GET: Mostrar clientes do agente logado (ou todos se admin)
    if agente:
        clientes_ativos = Cliente.objects.filter(agente=agente, status='ativo').order_by('nome')
        agentes = Agente.objects.filter(ativo=True).order_by('nome')
    else:
        clientes_ativos = Cliente.objects.filter(status='ativo').order_by('nome')
        agentes = Agente.objects.filter(ativo=True).order_by('nome')

    return render(request, 'core/lancar_pagamento.html', {
        'clientes': clientes_ativos,
        'agentes': agentes,
    })


# ====================== DASHBOARD DO AGENTE ======================
@login_required
def dashboard_agente(request):
    try:
        agente = request.user.agente
    except Agente.DoesNotExist:
        messages.error(request, 'Você não está associado a um agente.')
        return redirect('login')

    clientes = Cliente.objects.filter(agente=agente)
    pagamentos = Pagamento.objects.filter(agente=agente, confirmado=True)

    total_clientes = clientes.count()
    total_quitados = clientes.filter(status='quitado').count()
    total_pago = pagamentos.aggregate(total=Sum('valor'))['total'] or Decimal('0')

    # Pagamentos recentes (últimos 10)
    pagamentos_recentes = pagamentos.order_by('-data_pagamento')[:10]

    # Clientes ativos com saldo
    clientes_ativos = clientes.filter(status='ativo').order_by('nome')

    context = {
        'agente': agente,
        'total_clientes': total_clientes,
        'total_quitados': total_quitados,
        'total_pago': total_pago,
        'pagamentos_recentes': pagamentos_recentes,
        'clientes_ativos': clientes_ativos,
    }
    return render(request, 'core/dashboard_agente.html', context)


# ====================== DASHBOARD (ADMIN) ======================
@admin_required
def dashboard(request):
    hoje = timezone.now().date()
    pagamentos_hoje = Pagamento.objects.filter(data_pagamento=hoje, confirmado=True)
    total_hoje = pagamentos_hoje.aggregate(total=models.Sum('valor'))['total'] or Decimal('0')

    inicio_semana = hoje - timedelta(days=hoje.weekday())
    pagamentos_semana = Pagamento.objects.filter(data_pagamento__gte=inicio_semana, confirmado=True)
    total_semana = pagamentos_semana.aggregate(total=models.Sum('valor'))['total'] or Decimal('0')

    inicio_mes = hoje.replace(day=1)
    pagamentos_mes = Pagamento.objects.filter(data_pagamento__gte=inicio_mes, confirmado=True)
    total_mes = pagamentos_mes.aggregate(total=models.Sum('valor'))['total'] or Decimal('0')

    agentes_hoje = []
    for agente in Agente.objects.filter(ativo=True):
        total_agente = pagamentos_hoje.filter(agente=agente).aggregate(total=models.Sum('valor'))['total'] or Decimal('0')
        meta = agente.meta_diaria
        atingiu = total_agente >= meta if meta > 0 else False
        percentual = (total_agente / meta * 100) if meta > 0 else 0
        agentes_hoje.append({
            'agente': agente,
            'total': total_agente,
            'meta': meta,
            'atingiu': atingiu,
            'percentual': min(percentual, 100),
        })

    ultimos_pagamentos = Pagamento.objects.filter(confirmado=True).order_by('-data_pagamento')[:10]

    context = {
        'total_hoje': total_hoje,
        'total_semana': total_semana,
        'total_mes': total_mes,
        'agentes_hoje': agentes_hoje,
        'ultimos_pagamentos': ultimos_pagamentos,
        'hoje': hoje,
    }
    return render(request, 'core/dashboard.html', context)


# ====================== EXTRATO DO CLIENTE ======================
def extrato_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    pagamentos = cliente.pagamentos.filter(confirmado=True).order_by('-data_pagamento')
    total_pago = cliente.total_pago()
    saldo = cliente.saldo_devedor

    context = {
        'cliente': cliente,
        'pagamentos': pagamentos,
        'total_pago': total_pago,
        'saldo': saldo,
    }
    return render(request, 'core/extrato_cliente.html', context)


# ====================== COMPROVATIVO MENSAL ======================
def comprovativo_mensal(request, cliente_id, mes=None, ano=None):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if mes is None or ano is None:
        hoje = timezone.now().date()
        mes = hoje.month
        ano = hoje.year

    data_inicio = datetime(ano, mes, 1).date()
    if mes == 12:
        data_fim = datetime(ano+1, 1, 1).date()
    else:
        data_fim = datetime(ano, mes+1, 1).date()

    pagamentos = cliente.pagamentos.filter(
        confirmado=True,
        data_pagamento__gte=data_inicio,
        data_pagamento__lt=data_fim
    ).order_by('data_pagamento')

    total_mes = pagamentos.aggregate(total=models.Sum('valor'))['total'] or Decimal('0')

    meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
             'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    nome_mes = meses[mes-1]

    context = {
        'cliente': cliente,
        'pagamentos': pagamentos,
        'total_mes': total_mes,
        'mes': mes,
        'ano': ano,
        'nome_mes': nome_mes,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    }
    return render(request, 'core/comprovativo_mensal.html', context)


# ====================== CHINA MALL DASHBOARD (APENAS ADMIN) ======================

# ====================== CHINA MALL DASHBOARD ======================
# Permite acesso a superusuários E utilizadores do grupo "ChinaMall"
def china_mall_dashboard(request):
    # Verificar permissões manualmente
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not (request.user.is_superuser or request.user.groups.filter(name='ChinaMall').exists()):
        messages.warning(request, 'Acesso restrito a utilizadores autorizados.')
        return redirect('lista_clientes')

    hoje = timezone.now().date()
    inicio_semana = hoje - timedelta(days=hoje.weekday())

    clientes_ativos = Cliente.objects.filter(status='ativo')
    clientes_quitados = Cliente.objects.filter(status='quitado')
    total_clientes = clientes_ativos.count()

    pagamentos_todos = Pagamento.objects.filter(confirmado=True)
    receita_total = pagamentos_todos.aggregate(total=Sum('valor'))['total'] or Decimal('0')

    pagamentos_semana = pagamentos_todos.filter(data_pagamento__gte=inicio_semana)
    receita_semana = pagamentos_semana.aggregate(total=Sum('valor'))['total'] or Decimal('0')
    meta_semanal = Decimal('50400.00')
    percentual_meta = float(receita_semana) / float(meta_semanal) * 100 if meta_semanal > 0 else 0

    inicio_mes = hoje.replace(day=1)
    pagamentos_mes = pagamentos_todos.filter(data_pagamento__gte=inicio_mes)
    receita_mes = pagamentos_mes.aggregate(total=Sum('valor'))['total'] or Decimal('0')

    valor_total_produtos = clientes_ativos.aggregate(total=Sum('valor_produto'))['total'] or Decimal('0')
    comissao_srg = valor_total_produtos * Decimal('0.20')
    saldo_china_mall = valor_total_produtos * Decimal('0.80')

    clientes_previsao = []
    for cliente in clientes_ativos:
        dias_rest = cliente.get_dias_restantes()
        semanas_rest = cliente.get_semanas_restantes()
        meses_rest = cliente.get_meses_restantes()
        deposito_diario = cliente.get_deposito_diario_esperado()
        comissao_cliente = cliente.valor_produto * Decimal('0.20')
        saldo_china_cliente = cliente.valor_produto * Decimal('0.80')
        clientes_previsao.append({
            'cliente': cliente,
            'dias_restantes': dias_rest,
            'semanas_restantes': semanas_rest,
            'meses_restantes': meses_rest,
            'deposito_diario': deposito_diario,
            'total_pago': cliente.total_pago(),
            'saldo': cliente.saldo_devedor,
            'comissao_srg': comissao_cliente,
            'saldo_china_mall': saldo_china_cliente,
        })

    context = {
        'total_clientes': total_clientes,
        'total_quitados': clientes_quitados.count(),
        'receita_total': float(receita_total),
        'receita_semana': float(receita_semana),
        'receita_mes': float(receita_mes),
        'meta_semanal': float(meta_semanal),
        'percentual_meta': percentual_meta,
        'comissao_srg': float(comissao_srg),
        'saldo_china_mall': float(saldo_china_mall),
        'clientes_previsao': clientes_previsao,
        'valor_total_produtos': float(valor_total_produtos),
    }
    return render(request, 'core/china_mall.html', context)
# ====================== BASE DE DADOS CLIENTES (APENAS ADMIN) ======================
@admin_required
def base_dados_clientes(request):
    clientes = Cliente.objects.all().order_by('nome')
    return render(request, 'core/base_dados_clientes.html', {'clientes': clientes})


# ====================== ADMINISTRAÇÃO FINANCEIRA ======================
# Permite acesso a superusuários E utilizadores do grupo "Financeiro"
# (NÃO USAR @admin_required AQUI)
def financeiro_dashboard(request):
    # Verificar permissões manualmente
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not (request.user.is_superuser or request.user.groups.filter(name='Financeiro').exists()):
        messages.warning(request, 'Acesso restrito a utilizadores autorizados.')
        return redirect('lista_clientes')

    hoje = timezone.now().date()
    inicio_mes = hoje.replace(day=1)
    inicio_semana = hoje - timedelta(days=hoje.weekday())

    # ========== PAGAMENTOS ==========
    pagamentos_mes = Pagamento.objects.filter(confirmado=True, data_pagamento__gte=inicio_mes)
    total_mes = pagamentos_mes.aggregate(total=Sum('valor'))['total'] or Decimal('0')

    pagamentos_semana = Pagamento.objects.filter(confirmado=True, data_pagamento__gte=inicio_semana)
    total_semana = pagamentos_semana.aggregate(total=Sum('valor'))['total'] or Decimal('0')

    pagamentos_todos = Pagamento.objects.filter(confirmado=True)
    total_geral = pagamentos_todos.aggregate(total=Sum('valor'))['total'] or Decimal('0')

    # ========== GANHOS SRG ==========
    srg_semanal = total_semana * Decimal('0.20')
    srg_diario_medio = srg_semanal / Decimal('7')
    srg_mensal = total_mes * Decimal('0.20')
    srg_total = total_geral * Decimal('0.20')

    # ========== CHINA MALL ==========
    china_mensal = total_mes * Decimal('0.80')

    # ========== SALÁRIOS ==========
    salarios_mes = SalarioAgente.objects.filter(mes=hoje.month, ano=hoje.year)
    total_salarios = salarios_mes.aggregate(total=Sum('valor'))['total'] or Decimal('0')

    # ========== DESPESAS ==========
    despesas_mes = Despesa.objects.filter(data__gte=inicio_mes)
    total_despesas = despesas_mes.aggregate(total=Sum('valor'))['total'] or Decimal('0')

    # ========== LUCRO LÍQUIDO ==========
    lucro_liquido = srg_mensal - total_salarios - total_despesas

    # ========== ADICIONAR DESPESA (POST) ==========
    if request.method == 'POST' and 'add_despesa' in request.POST:
        descricao = request.POST.get('descricao')
        valor = request.POST.get('valor')
        categoria = request.POST.get('categoria')
        data = request.POST.get('data') or hoje
        if descricao and valor:
            Despesa.objects.create(
                descricao=descricao,
                valor=Decimal(valor),
                categoria=categoria,
                data=data
            )
            messages.success(request, 'Despesa adicionada com sucesso!')
            return redirect('admin_financeira')

    # ========== CONTEXTO ==========
    context = {
        'srg_diario': srg_diario_medio,
        'srg_semanal': srg_semanal,
        'srg_mensal': srg_mensal,
        'srg_total': srg_total,
        'china_mensal': china_mensal,
        'total_salarios': total_salarios,
        'total_despesas': total_despesas,
        'lucro_liquido': lucro_liquido,
        'despesas': despesas_mes.order_by('-data')[:20],
        'salarios': salarios_mes,
        'hoje': hoje,
        'categorias': Despesa.CATEGORIA_CHOICES,
    }
    return render(request, 'core/admin_financeira.html', context)


# ====================== ADICIONAR DESPESA ======================
# Permite acesso a superusuários E utilizadores do grupo "Financeiro"
def adicionar_despesa(request):
    # Verificar permissões manualmente
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not (request.user.is_superuser or request.user.groups.filter(name='Financeiro').exists()):
        messages.warning(request, 'Acesso restrito a utilizadores autorizados.')
        return redirect('lista_clientes')

    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        categoria = request.POST.get('categoria')
        valor = request.POST.get('valor')
        data = request.POST.get('data')
        pago = request.POST.get('pago') == 'on'
        observacao = request.POST.get('observacao', '')

        if descricao and categoria and valor:
            Despesa.objects.create(
                descricao=descricao,
                categoria=categoria,
                valor=valor,
                data=data or timezone.now().date(),
                pago=pago,
                observacao=observacao
            )
            messages.success(request, 'Despesa adicionada com sucesso!')
            return redirect('admin_financeira')
        else:
            messages.error(request, 'Preencha todos os campos obrigatórios.')

    return render(request, 'core/adicionar_despesa.html')


# ====================== ADMIN DASHBOARD (APENAS ADMIN) ======================
@admin_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('dashboard_agente')

    # Dashboard para administrador com todos os dados
    agentes = Agente.objects.all()
    clientes = Cliente.objects.all()
    pagamentos = Pagamento.objects.filter(confirmado=True)

    total_pago = pagamentos.aggregate(total=Sum('valor'))['total'] or Decimal('0')
    total_clientes = clientes.count()
    total_agentes = agentes.count()

    # Desempenho por agente
    desempenho = []
    for agente in agentes:
        qtd_clientes = clientes.filter(agente=agente).count()
        total_agente = pagamentos.filter(agente=agente).aggregate(total=Sum('valor'))['total'] or Decimal('0')
        desempenho.append({
            'agente': agente,
            'total_clientes': qtd_clientes,
            'total_pago': total_agente,
        })

    context = {
        'total_pago': total_pago,
        'total_clientes': total_clientes,
        'total_agentes': total_agentes,
        'desempenho': desempenho,
        'pagamentos_recentes': pagamentos.order_by('-data_pagamento')[:10],
        'clientes_recentes': clientes.order_by('-data_registo')[:10],
    }
    return render(request, 'core/admin_dashboard.html', context)


# ====================== REDIRECIONAMENTO DE LOGIN ======================
def login_redirect(request):
    if request.user.is_authenticated:
        # 1. Admin → menu principal
        if request.user.is_superuser:
            return redirect('menu_principal')
        
        # 2. Financeiro → página financeira
        if request.user.groups.filter(name='Financeiro').exists():
            return redirect('admin_financeira')
        
        # 3. China Mall → página China Mall
        if request.user.groups.filter(name='ChinaMall').exists():
            return redirect('china_mall_dashboard')
        
        # 4. Agente → lista de clientes
        return redirect('lista_clientes')
    
    return redirect('login')

# ====================== MENU PRINCIPAL (APENAS ADMIN) ======================
@admin_required
def menu_principal(request):
    return render(request, 'core/menu_principal.html')