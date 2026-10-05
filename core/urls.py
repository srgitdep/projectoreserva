# core/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ========== REDIRECIONAMENTO ==========
    path('', views.login_redirect, name='home'),                    # <-- raiz vai para login
    path('login-redirect/', views.login_redirect, name='login_redirect'),

    # ========== AUTENTICAÇÃO ==========
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # ========== AGENTES ==========
    path('agentes/', views.lista_agentes, name='lista_agentes'),
    path('agentes/cadastrar/', views.cadastrar_agente, name='cadastrar_agente'),

    # ========== CLIENTES ==========
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/cadastrar/', views.cadastrar_cliente, name='cadastrar_cliente'),

    # ========== PAGAMENTOS ==========
    path('pagamento/lancar/', views.lancar_pagamento, name='lancar_pagamento'),

    # ========== DASHBOARDS ==========
    path('dashboard/', views.dashboard, name='dashboard'),                 # admin
    path('meu-dashboard/', views.dashboard_agente, name='dashboard_agente'),

    # ========== EXTRATO E COMPROVATIVO ==========
    path('cliente/<int:cliente_id>/extrato/', views.extrato_cliente, name='extrato_cliente'),
    path('cliente/<int:cliente_id>/comprovativo/<int:mes>/<int:ano>/', views.comprovativo_mensal, name='comprovativo_mensal'),
    path('cliente/<int:cliente_id>/comprovativo/', views.comprovativo_mensal, name='comprovativo_mensal_atual'),

    # ========== CHINA MALL ==========
    path('china-mall/', views.china_mall_dashboard, name='china_mall_dashboard'),

    # ========== BASE DE DADOS ==========
    path('base-dados-clientes/', views.base_dados_clientes, name='base_dados_clientes'),

    # ========== ADMIN FINANCEIRA ==========
    path('admin-financeira/', views.financeiro_dashboard, name='admin_financeira'),
    path('despesa/adicionar/', views.adicionar_despesa, name='adicionar_despesa'),
    path('menu/', views.menu_principal, name='menu_principal'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
]