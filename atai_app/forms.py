from django import forms
from .models import Profile


class EmailForm(forms.Form):
    email = forms.EmailField(label='Email')


class ProfileForm(forms.ModelForm):
    trade_quantity = forms.IntegerField(label='Trade Quantity (in USDC) ', required=False)

    class Meta:
        model = Profile
        fields = ['trade_btc', 'trade_eth', 'risk_tolerance', 'trade_quantity']
