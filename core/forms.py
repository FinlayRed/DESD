from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import OrderItem, Producer, ProducerContent, Product, SurplusListing


User = get_user_model()


class ProducerLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    error_messages = {
        "invalid_login": "Please enter a correct email and password.",
        "not_producer": "This account is not registered as a producer.",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                raise forms.ValidationError(self.error_messages["invalid_login"])

            self.user_cache = authenticate(
                self.request,
                username=user.get_username(),
                password=password,
            )

            if self.user_cache is None:
                raise forms.ValidationError(self.error_messages["invalid_login"])

            if not Producer.objects.filter(user=self.user_cache).exists():
                raise forms.ValidationError(self.error_messages["not_producer"])

        return cleaned_data

    def get_user(self):
        return self.user_cache


class ProducerRegisterForm(UserCreationForm):
    business_name = forms.CharField(max_length=100)
    postcode = forms.CharField(max_length=10)
    organic = forms.BooleanField(required=False)
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_postcode(self):
        return self.cleaned_data["postcode"].strip().upper()

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.email = email
        user.username = email
        if commit:
            user.save()
            Producer.objects.create(
                user=user,
                business_name=self.cleaned_data["business_name"],
                postcode=self.cleaned_data["postcode"],
                organic=self.cleaned_data["organic"],
            )
        return user


class CustomerLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    error_messages = {
        "invalid_login": "Please enter a correct email and password.",
        "is_producer": "This account is registered as a producer. Please use producer login.",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                raise forms.ValidationError(self.error_messages["invalid_login"])

            self.user_cache = authenticate(
                self.request,
                username=user.get_username(),
                password=password,
            )

            if self.user_cache is None:
                raise forms.ValidationError(self.error_messages["invalid_login"])

            if Producer.objects.filter(user=self.user_cache).exists():
                raise forms.ValidationError(self.error_messages["is_producer"])

        return cleaned_data

    def get_user(self):
        return self.user_cache


class CustomerRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.email = email
        user.username = email
        if commit:
            user.save()
        return user


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "category",
            "price",
            "stock_quantity",
            "minimum_order_quantity",
            "lead_time_hours",
            "available_from",
            "available_to",
            "harvest_date",
            "best_before_date",
            "farm_origin",
            "seasonal_highlight",
            "organic",
            "allergen_info",
            "storage_guidance",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Organic Heritage Tomatoes"}),
            "description": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Describe flavour profile, texture, suggested pairings, or what makes this product special..."
            }),
            "price": forms.NumberInput(attrs={
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0",
                "class": "has-prefix"
            }),
            "stock_quantity": forms.NumberInput(attrs={"placeholder": "0", "min": "0"}),
            "minimum_order_quantity": forms.NumberInput(attrs={"placeholder": "1", "min": "1"}),
            "lead_time_hours": forms.NumberInput(attrs={"placeholder": "24", "min": "0"}),
            "available_from": forms.DateInput(attrs={"type": "date"}),
            "available_to": forms.DateInput(attrs={"type": "date"}),
            "harvest_date": forms.DateInput(attrs={"type": "date"}),
            "best_before_date": forms.DateInput(attrs={"type": "date"}),
            "farm_origin": forms.TextInput(attrs={"placeholder": "e.g., Sunnyside Farm, Somerset"}),
            "seasonal_highlight": forms.TextInput(attrs={"placeholder": "e.g., Summer favourite"}),
            "allergen_info": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "List any allergens: contains nuts, produced in facility that handles gluten..."
            }),
            "storage_guidance": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "e.g., Keep refrigerated at 2-5°C, consume within 3 days of opening"
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        available_from = cleaned_data.get("available_from")
        available_to = cleaned_data.get("available_to")
        harvest_date = cleaned_data.get("harvest_date")
        best_before_date = cleaned_data.get("best_before_date")

        if available_from and available_to and available_to < available_from:
            self.add_error("available_to", "Available to date cannot be before available from date.")

        if harvest_date and best_before_date and best_before_date < harvest_date:
            self.add_error("best_before_date", "Best before date cannot be before the harvest date.")

        return cleaned_data


class ProducerProfileForm(forms.ModelForm):
    class Meta:
        model = Producer
        fields = ["business_name", "postcode", "organic"]

    def clean_postcode(self):
        return self.cleaned_data["postcode"].strip().upper()


class ProducerOrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ["status", "producer_notes"]
        widgets = {
            "producer_notes": forms.Textarea(attrs={"rows": 4}),
        }


class SurplusListingForm(forms.ModelForm):
    class Meta:
        model = SurplusListing
        fields = [
            "product",
            "quantity",
            "discounted_price",
            "available_until",
            "note",
            "is_active",
        ]
        widgets = {
            "available_until": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "note": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, producer=None, **kwargs):
        self.producer = producer
        super().__init__(*args, **kwargs)
        if producer is not None:
            self.fields["product"].queryset = Product.objects.filter(producer=producer).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        discounted_price = cleaned_data.get("discounted_price")

        if product and discounted_price is not None and discounted_price > product.price:
            self.add_error("discounted_price", "Discounted price cannot be more than the product price.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        product = self.cleaned_data["product"]
        discounted_price = self.cleaned_data["discounted_price"]

        instance.original_price = product.price
        if product.price > 0:
            discount = ((product.price - discounted_price) / product.price) * Decimal("100")
            if discounted_price == product.price:
                instance.discount_percent = 0
            else:
                instance.discount_percent = max(
                    1,
                    min(90, int(discount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))),
                )
        else:
            instance.discount_percent = 0

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ProducerContentForm(forms.ModelForm):
    class Meta:
        model = ProducerContent
        fields = ["content_type", "title", "season", "product", "summary", "body", "is_published"]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 2}),
            "body": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, producer=None, **kwargs):
        self.producer = producer
        super().__init__(*args, **kwargs)
        if producer is not None:
            self.fields["product"].queryset = Product.objects.filter(producer=producer).order_by("name")
