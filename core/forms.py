from django import forms

from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "price",
            "category",
            "available_from",
            "available_to",
            "is_active",
        ]
        widgets = {
            "available_from": forms.DateInput(attrs={"type": "date"}),
            "available_to": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        available_from = cleaned_data.get("available_from")
        available_to = cleaned_data.get("available_to")

        if available_from and available_to and available_to < available_from:
            self.add_error("available_to", "Available to date cannot be before available from date.")

        return cleaned_data
