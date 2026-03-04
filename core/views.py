from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from .forms import ProducerLoginForm, ProducerRegisterForm, ProductForm
from .models import Producer, Product


class HomeView(TemplateView):
    template_name = "core/home.html"


class ProducerLoginView(FormView):
    template_name = "core/producer_login.html"
    form_class = ProducerLoginForm
    success_url = reverse_lazy("core:product-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        login(self.request, form.get_user())
        return super().form_valid(form)


class ProducerRegisterView(FormView):
    template_name = "core/producer_register.html"
    form_class = ProducerRegisterForm
    success_url = reverse_lazy("core:product-list")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


class ProductOwnerQuerysetMixin:
    def get_queryset(self):
        queryset = Product.objects.all()
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(producer__user=self.request.user)


class ProductListView(LoginRequiredMixin, ProductOwnerQuerysetMixin, ListView):
    model = Product
    template_name = "core/product_list.html"
    context_object_name = "products"
    login_url = "/producer/login/"


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "core/product_form.html"
    success_url = reverse_lazy("core:product-list")
    login_url = "/producer/login/"

    def form_valid(self, form):
        try:
            form.instance.producer = self.request.user.producer
        except Producer.DoesNotExist:
            messages.error(self.request, "Please register as a producer before creating products.")
            return redirect("core:producer-register")
        return super().form_valid(form)


class ProductUpdateView(LoginRequiredMixin, ProductOwnerQuerysetMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "core/product_form.html"
    success_url = reverse_lazy("core:product-list")
    login_url = "/producer/login/"


class ProductDeleteView(LoginRequiredMixin, ProductOwnerQuerysetMixin, DeleteView):
    model = Product
    template_name = "core/product_confirm_delete.html"
    success_url = reverse_lazy("core:product-list")
    login_url = "/producer/login/"
