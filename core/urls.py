from django.urls import path

from .views import (
    CustomerCheckoutView,
    CustomerLoginView,
    CustomerProductBrowseView,
    CustomerRegisterView,
    HomeView,
    ProducerLoginView,
    ProducerRegisterView,
    ProductCreateView,
    ProductDeleteView,
    ProductListView,
    ProductUpdateView,
    user_logout_view,
)

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("customer/products/", CustomerProductBrowseView.as_view(), name="customer-product-list"),
    path("customer/checkout/", CustomerCheckoutView.as_view(), name="customer-checkout"),
    path("customer/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("customer/register/", CustomerRegisterView.as_view(), name="customer-register"),
    path("customer/logout/", user_logout_view, name="customer-logout"),
    path("producer/login/", ProducerLoginView.as_view(), name="producer-login"),
    path("producer/register/", ProducerRegisterView.as_view(), name="producer-register"),
    path("producer/products/", ProductListView.as_view(), name="product-list"),
    path("producer/products/new/", ProductCreateView.as_view(), name="product-create"),
    path("producer/products/<int:pk>/edit/", ProductUpdateView.as_view(), name="product-update"),
    path("producer/products/<int:pk>/delete/", ProductDeleteView.as_view(), name="product-delete"),
]
