from django.contrib import admin
from .models import Cliente, Pagamento, Agente

admin.site.register(Cliente)
admin.site.register(Pagamento)
admin.site.register(Agente)