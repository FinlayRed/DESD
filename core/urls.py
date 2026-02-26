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

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("producer/login/", ProducerLoginView.as_view(), name="producer-login"),
    path("producer/register/", ProducerRegisterView.as_view(), name="producer-register"),
    path("producer/products/", ProductListView.as_view(), name="product-list"),
    path("producer/products/new/", ProductCreateView.as_view(), name="product-create"),
    path("producer/products/<int:pk>/edit/", ProductUpdateView.as_view(), name="product-update"),
    path("producer/products/<int:pk>/delete/", ProductDeleteView.as_view(), name="product-delete"),
]
