from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from .forms import (
    CustomerLoginForm,
    CustomerRegisterForm,
    ProducerLoginForm,
    ProducerRegisterForm,
    ProductForm,
)
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


class CustomerLoginView(FormView):
    template_name = "core/customer_login.html"
    form_class = CustomerLoginForm
    success_url = reverse_lazy("core:customer-product-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        login(self.request, form.get_user())
        return super().form_valid(form)


class CustomerRegisterView(FormView):
    template_name = "core/customer_register.html"
    form_class = CustomerRegisterForm
    success_url = reverse_lazy("core:customer-product-list")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


def user_logout_view(request):
    logout(request)
    return redirect("core:home")


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


class CustomerProductBrowseView(ListView):
    model = Product
    template_name = "core/customer_product_list.html"
    context_object_name = "products"

    category_keys = [
        "vegetables",
        "dairy",
        "bakery",
        "preserves",
        "seasonal specialities",
    ]

    def get_queryset(self):
        queryset = (
            Product.objects.filter(is_active=True)
            .select_related("producer", "category")
            .order_by("name")
        )
        query = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "").strip().lower()

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(producer__business_name__icontains=query)
            )
        if category:
            queryset = queryset.filter(category__name__iexact=category)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        products = list(context["products"])
        grouped = {key: [] for key in self.category_keys}

        for product in products:
            key = (product.category.name if product.category else "").strip().lower()
            if key not in grouped:
                continue
            if product.available_from and product.available_to:
                if product.available_from <= today <= product.available_to:
                    product.seasonal_status = "In season"
                elif today < product.available_from:
                    product.seasonal_status = "Upcoming season"
                else:
                    product.seasonal_status = "Out of season"
            elif product.available_from and today < product.available_from:
                product.seasonal_status = "Upcoming season"
            else:
                product.seasonal_status = "Seasonal dates not set"
            grouped[key].append(product)

        context["grouped_products"] = grouped
        context["query"] = self.request.GET.get("q", "").strip()
        context["active_category"] = self.request.GET.get("category", "").strip().lower()
        context["category_keys"] = self.category_keys
        return context


class CustomerCheckoutView(TemplateView):
    template_name = "core/customer_checkout.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_ids = [value for value in self.request.GET.getlist("items") if value.isdigit()]
        selected_products = list(
            Product.objects.filter(pk__in=selected_ids, is_active=True)
            .select_related("producer", "category")
            .order_by("producer__business_name", "name")
        )

        vendor_groups = {}
        for product in selected_products:
            vendor_key = product.producer_id
            if vendor_key not in vendor_groups:
                vendor_groups[vendor_key] = {"producer": product.producer, "items": []}
            vendor_groups[vendor_key]["items"].append(product)

        context["selected_products"] = selected_products
        context["vendor_groups"] = list(vendor_groups.values())
        context["is_multi_vendor"] = len(vendor_groups) > 1
        return context
