"""
URL Configuration for Bristol Regional Food Network
Combines customer browsing, cart, checkout, producer management, and order tracking.
"""

from django.urls import path

from .views import (
    # Home
    HomeView,
    # Customer Auth
    CustomerLoginView,
    CustomerRegisterView,
    # Producer Auth
    ProducerLoginView,
    ProducerRegisterView,
    # Logout (shared)
    user_logout_view,
    # Customer Product Browsing
    CustomerProductBrowseView,
    # Producer Product Management
    ProductListView,
    ProductCreateView,
    ProductUpdateView,
    ProductDeleteView,
)

from .order_views import (
    # Cart
    CartView,
    CartTestView,
    AddToCartView,
    UpdateCartView,
    RemoveFromCartView,
    # Checkout & Payment
    CheckoutView,
    PaymentView,
    PaymentSuccessView,
    # Customer Orders
    CustomerOrderListView,
    CustomerOrderDetailView,
    # Producer Orders
    ProducerOrderListView,
    ProducerOrderDetailView,
    UpdateOrderStatusView,
    # Webhooks
    stripe_webhook,
)

app_name = "core"

urlpatterns = [
    # =========================================================================
    # HOME
    # =========================================================================
    path("", HomeView.as_view(), name="home"),

    # =========================================================================
    # CUSTOMER AUTHENTICATION
    # =========================================================================
    path("customer/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("customer/register/", CustomerRegisterView.as_view(), name="customer-register"),
    path("customer/logout/", user_logout_view, name="customer-logout"),

    # =========================================================================
    # CUSTOMER PRODUCT BROWSING
    # =========================================================================
    path("customer/products/", CustomerProductBrowseView.as_view(), name="customer-product-list"),

    # =========================================================================
    # SHOPPING CART
    # =========================================================================
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/test/", CartTestView.as_view(), name="cart-test"),  # DEV ONLY
    path("cart/add/<int:product_id>/", AddToCartView.as_view(), name="cart-add"),
    path("cart/update/<int:product_id>/", UpdateCartView.as_view(), name="cart-update"),
    path("cart/remove/<int:product_id>/", RemoveFromCartView.as_view(), name="cart-remove"),

    # =========================================================================
    # CHECKOUT & PAYMENT
    # =========================================================================
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("customer/checkout/", CheckoutView.as_view(), name="customer-checkout"),  # Alias for compatibility
    path("payment/<int:order_id>/", PaymentView.as_view(), name="payment"),
    path("payment/<int:order_id>/success/", PaymentSuccessView.as_view(), name="payment-success"),

    # =========================================================================
    # CUSTOMER ORDERS
    # =========================================================================
    path("orders/", CustomerOrderListView.as_view(), name="customer-orders"),
    path("orders/<int:pk>/", CustomerOrderDetailView.as_view(), name="customer-order-detail"),

    # =========================================================================
    # PRODUCER AUTHENTICATION
    # =========================================================================
    path("producer/login/", ProducerLoginView.as_view(), name="producer-login"),
    path("producer/register/", ProducerRegisterView.as_view(), name="producer-register"),

    # =========================================================================
    # PRODUCER PRODUCT MANAGEMENT
    # =========================================================================
    path("producer/products/", ProductListView.as_view(), name="product-list"),
    path("producer/products/new/", ProductCreateView.as_view(), name="product-create"),
    path("producer/products/<int:pk>/edit/", ProductUpdateView.as_view(), name="product-update"),
    path("producer/products/<int:pk>/delete/", ProductDeleteView.as_view(), name="product-delete"),

    # =========================================================================
    # PRODUCER ORDER MANAGEMENT
    # =========================================================================
    path("producer/orders/", ProducerOrderListView.as_view(), name="producer-orders"),
    path("producer/orders/<int:pk>/", ProducerOrderDetailView.as_view(), name="producer-order-detail"),
    path("producer/orders/<int:order_id>/update-status/", UpdateOrderStatusView.as_view(), name="producer-order-status"),

    # =========================================================================
    # WEBHOOKS (Stripe)
    # =========================================================================
    path("webhook/stripe/", stripe_webhook, name="stripe-webhook"),
]