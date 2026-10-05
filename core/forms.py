from django import forms
from .models import Pagamento, Cliente

class PagamentoForm(forms.ModelForm):
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.filter(ativo=True),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    valor = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Pagamento
        fields = ['cliente', 'valor']