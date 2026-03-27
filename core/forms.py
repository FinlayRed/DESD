"""
Forms for Bristol Regional Food Network
Includes authentication, product management, and checkout forms.
"""

from datetime import timedelta

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

from .models import Order, Producer, Product


User = get_user_model()


# =============================================================================
# PRODUCER AUTHENTICATION
# =============================================================================

class ProducerLoginForm(forms.Form):
    """
    Email-based login for producers.
    Validates that the account is registered as a producer.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "placeholder": "you@example.com",
            "autocomplete": "email",
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Your password",
            "autocomplete": "current-password",
        })
    )

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
            # Find user by email
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                raise forms.ValidationError(self.error_messages["invalid_login"])

            # Authenticate
            self.user_cache = authenticate(
                self.request,
                username=user.get_username(),
                password=password,
            )

            if self.user_cache is None:
                raise forms.ValidationError(self.error_messages["invalid_login"])

            # Check if user is a producer
            if not Producer.objects.filter(user=self.user_cache).exists():
                raise forms.ValidationError(self.error_messages["not_producer"])

        return cleaned_data

    def get_user(self):
        return self.user_cache


class ProducerRegisterForm(UserCreationForm):
    """
    Registration form for new producers.
    Creates both User and Producer records.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "placeholder": "you@example.com",
        })
    )
    business_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            "placeholder": "Your Farm or Business Name",
        })
    )
    postcode = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            "placeholder": "BS1 4DJ",
        }),
        help_text="Must be within 20 miles of Bristol",
    )
    organic = forms.BooleanField(
        required=False,
        label="Certified Organic Producer",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_postcode(self):
        postcode = self.cleaned_data["postcode"].strip().upper()
        # Basic UK postcode validation
        if len(postcode) < 5 or len(postcode) > 8:
            raise forms.ValidationError("Please enter a valid UK postcode.")
        return postcode

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.email = email
        user.username = email  # Use email as username
        if commit:
            user.save()
            Producer.objects.create(
                user=user,
                business_name=self.cleaned_data["business_name"],
                postcode=self.cleaned_data["postcode"],
                organic=self.cleaned_data["organic"],
            )
        return user


# =============================================================================
# CUSTOMER AUTHENTICATION
# =============================================================================

class CustomerLoginForm(forms.Form):
    """
    Email-based login for customers.
    Prevents producers from using customer login.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "placeholder": "you@example.com",
            "autocomplete": "email",
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Your password",
            "autocomplete": "current-password",
        })
    )

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
            # Find user by email
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                raise forms.ValidationError(self.error_messages["invalid_login"])

            # Authenticate
            self.user_cache = authenticate(
                self.request,
                username=user.get_username(),
                password=password,
            )

            if self.user_cache is None:
                raise forms.ValidationError(self.error_messages["invalid_login"])

            # Check if user is a producer (should use producer login)
            if Producer.objects.filter(user=self.user_cache).exists():
                raise forms.ValidationError(self.error_messages["is_producer"])

        return cleaned_data

    def get_user(self):
        return self.user_cache


class CustomerRegisterForm(UserCreationForm):
    """
    Registration form for new customers.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "placeholder": "you@example.com",
        })
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.email = email
        user.username = email  # Use email as username
        if commit:
            user.save()
        return user


# =============================================================================
# PRODUCT MANAGEMENT
# =============================================================================

class ProductForm(forms.ModelForm):
    """
    Form for creating and editing products.
    Includes seasonal date validation.
    """

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "price",
            "stock_quantity",
            "category",
            "available_from",
            "available_to",
            "organic",
            "allergen_info",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Product name",
            }),
            "description": forms.Textarea(attrs={
                "placeholder": "Describe your product...",
                "rows": 4,
            }),
            "price": forms.NumberInput(attrs={
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0",
            }),
            "stock_quantity": forms.NumberInput(attrs={
                "placeholder": "0",
                "min": "0",
            }),
            "available_from": forms.DateInput(attrs={
                "type": "date",
            }),
            "available_to": forms.DateInput(attrs={
                "type": "date",
            }),
            "allergen_info": forms.Textarea(attrs={
                "placeholder": "List any allergens (e.g., Contains: Milk, Eggs)",
                "rows": 2,
            }),
        }
        help_texts = {
            "stock_quantity": "Number of units available for sale",
            "available_from": "Leave blank if always available",
            "available_to": "Leave blank if no end date",
            "allergen_info": "Important for FSA compliance",
        }

    def clean(self):
        cleaned_data = super().clean()
        available_from = cleaned_data.get("available_from")
        available_to = cleaned_data.get("available_to")

        # Validate date range
        if available_from and available_to:
            if available_to < available_from:
                self.add_error(
                    "available_to",
                    "End date cannot be before start date."
                )

        return cleaned_data

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is not None and price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price

    def clean_stock_quantity(self):
        stock = self.cleaned_data.get("stock_quantity")
        if stock is not None and stock < 0:
            raise forms.ValidationError("Stock quantity cannot be negative.")
        return stock


# =============================================================================
# CHECKOUT
# =============================================================================

class CheckoutForm(forms.Form):
    """
    Checkout form with delivery details and 48hr lead time validation.
    """
    postcode = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            "placeholder": "e.g., BS1 4DJ",
        }),
        help_text="Used to calculate food miles for environmental reporting",
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "placeholder": "Full delivery address if applicable",
            "rows": 3,
        }),
        label="Delivery Address (optional)",
    )
    collection_date = forms.DateField(
        widget=forms.DateInput(attrs={
            "type": "date",
        }),
        label="Preferred Collection Date",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set minimum date to 48 hours from now
        min_date = (timezone.now() + timedelta(hours=48)).date()
        self.fields["collection_date"].widget.attrs["min"] = min_date.isoformat()
        self.min_collection_date = min_date

    def clean_postcode(self):
        postcode = self.cleaned_data["postcode"].strip().upper()
        if len(postcode) < 5 or len(postcode) > 8:
            raise forms.ValidationError("Please enter a valid UK postcode.")
        return postcode

    def clean_collection_date(self):
        collection_date = self.cleaned_data.get("collection_date")
        min_date = (timezone.now() + timedelta(hours=48)).date()

        if collection_date and collection_date < min_date:
            raise forms.ValidationError(
                f"Collection date must be at least 48 hours from now. "
                f"Earliest available: {min_date.strftime('%d %b %Y')}."
            )

        return collection_date


# =============================================================================
# ORDER MANAGEMENT (Producer)
# =============================================================================

class OrderStatusForm(forms.Form):
    """
    Form for producers to update order status.
    """
    STATUS_CHOICES = [
        ("processing", "Processing"),
        ("ready", "Ready for Collection"),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            "class": "status-select",
        }),
    )


class AddToCartForm(forms.Form):
    """
    Form for adding products to cart.
    """
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            "class": "quantity-input",
            "min": "1",
        }),
    )

    def __init__(self, *args, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        if product:
            self.fields["quantity"].widget.attrs["max"] = product.stock_quantity

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")

        if self.product:
            if quantity > self.product.stock_quantity:
                raise forms.ValidationError(
                    f"Only {self.product.stock_quantity} available."
                )

        return quantity


class UpdateCartForm(forms.Form):
    """
    Form for updating cart item quantity.
    """
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            "class": "quantity-input",
            "min": "0",
        }),
    )

    def __init__(self, *args, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        if product:
            self.fields["quantity"].widget.attrs["max"] = product.stock_quantity

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")

        if self.product and quantity > 0:
            if quantity > self.product.stock_quantity:
                raise forms.ValidationError(
                    f"Only {self.product.stock_quantity} available."
                )

        return quantity