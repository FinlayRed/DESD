from django.urls import path

from .views import (
    HomeView,
    ProducerLoginView,
    ProducerRegisterView,
    ProductCreateView,
    ProductDeleteView,
    ProductListView,
    ProductUpdateView,
)

from .order_views import (
    # Cart
    CartView,
    CartTestView,
    AddToCartView,
    UpdateCartView,
    RemoveFromCartView,
    # Checkout
    CheckoutView,
    # Payment
    PaymentView,
    CreatePaymentIntentView,
    PaymentSuccessView,
    stripe_webhook,
    # Customer Orders
    CustomerOrderListView,
    CustomerOrderDetailView,
    # Producer Orders
    ProducerOrderListView,
    ProducerOrderDetailView,
    UpdateOrderStatusView,
)

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("producer/login/", ProducerLoginView.as_view(), name="producer-login"),
    path("producer/register/", ProducerRegisterView.as_view(), name="producer-register"),
    path("producer/products/", ProductListView.as_view(), name="product-list"),
    path("producer/products/new/", ProductCreateView.as_view(), name="product-create"),
    path("producer/products/<int:pk>/edit/", ProductUpdateView.as_view(), name="product-update"),
    path("producer/products/<int:pk>/delete/", ProductDeleteView.as_view(), name="product-delete"),
    
    #shopping basket / checkout
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/add/<int:product_id>/", AddToCartView.as_view(), name="cart-add"),
    path("cart/update/<int:product_id>/", UpdateCartView.as_view(), name="cart-update"),
    path("cart/remove/<int:product_id>/", RemoveFromCartView.as_view(), name="cart-remove"),
    path("cart/test/", CartTestView.as_view(), name="cart-test"),
    
    # checout (handles single and multi-vendor)
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    
    # payment processing 
    path("payment/<int:order_id>/", PaymentView.as_view(), name="payment"),
    path("payment/<int:order_id>/create-intent/", CreatePaymentIntentView.as_view(), name="payment-create-intent"),
    path("payment/<int:order_id>/success/", PaymentSuccessView.as_view(), name="payment-success"),
    path("webhook/stripe/", stripe_webhook, name="stripe-webhook"),
    
    # customer order tracking
    path("orders/", CustomerOrderListView.as_view(), name="customer-orders"),
    path("orders/<int:pk>/", CustomerOrderDetailView.as_view(), name="customer-order-detail"),
    
    # producer order management
    path("producer/orders/", ProducerOrderListView.as_view(), name="producer-orders"),
    path("producer/orders/<int:pk>/", ProducerOrderDetailView.as_view(), name="producer-order-detail"),
    path("producer/orders/<int:order_id>/update-status/", UpdateOrderStatusView.as_view(), name="producer-order-status"),

]
