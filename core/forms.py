from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Producer, Product


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
