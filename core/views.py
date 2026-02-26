from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from .forms import ProductForm
from .models import Product


class HomeView(TemplateView):
    template_name = "core/home.html"


class ProducerLoginView(TemplateView):
    template_name = "core/producer_login.html"


class ProducerRegisterView(TemplateView):
    template_name = "core/producer_register.html"


class ProductOwnerQuerysetMixin:
    def get_queryset(self):
        queryset = Product.objects.all()
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(owner=self.request.user)


class ProductListView(LoginRequiredMixin, ProductOwnerQuerysetMixin, ListView):
    model = Product
    template_name = "core/product_list.html"
    context_object_name = "products"
    login_url = "/admin/login/"


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "core/product_form.html"
    success_url = reverse_lazy("core:product-list")
    login_url = "/admin/login/"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class ProductUpdateView(LoginRequiredMixin, ProductOwnerQuerysetMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "core/product_form.html"
    success_url = reverse_lazy("core:product-list")
    login_url = "/admin/login/"


class ProductDeleteView(LoginRequiredMixin, ProductOwnerQuerysetMixin, DeleteView):
    model = Product
    template_name = "core/product_confirm_delete.html"
    success_url = reverse_lazy("core:product-list")
    login_url = "/admin/login/"
