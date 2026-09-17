from django import forms
from .models import Service, Payment


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "price", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Hair Wash"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0.00", "step": "0.01", "min": "0"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is not None and price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price


class AddServiceToTicketForm(forms.Form):
    service = forms.ModelChoiceField(
        queryset=Service.objects.filter(is_active=True),
        empty_label="-- Select Service --",
        widget=forms.Select(attrs={"class": "form-control"})
    )


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["method", "amount"]
        widgets = {
            "method": forms.Select(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount < 0:
            raise forms.ValidationError("Amount cannot be negative.")
        return amount
