from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from .forms import (
    ProducerContentForm,
    ProducerLoginForm,
    ProducerOrderItemForm,
    ProducerProfileForm,
    ProducerRegisterForm,
    ProductForm,
    SurplusListingForm,
)
from .models import Order, OrderItem, Producer, ProducerContent, ProducerSettlement, Product, SurplusListing
from .services import item_food_miles, order_item_requires_attention, sync_producer_settlements


class HomeView(TemplateView):
    template_name = "core/home.html"


class ProducerAccessMixin(LoginRequiredMixin):
    login_url = "/producer/login/"
    producer = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        try:
            self.producer = request.user.producer
        except Producer.DoesNotExist:
            messages.error(request, "Please register as a producer to access the producer workspace.")
            return redirect("core:producer-register")
        return super().dispatch(request, *args, **kwargs)


class ProducerOwnedFormMixin:
    producer = None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["producer"] = self.producer
        return kwargs


class ProducerLoginView(FormView):
    template_name = "core/producer_login.html"
    form_class = ProducerLoginForm
    success_url = reverse_lazy("core:dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        login(self.request, form.get_user())
        messages.success(self.request, "Welcome back. Your producer dashboard is ready.")
        return super().form_valid(form)


class ProducerRegisterView(FormView):
    template_name = "core/producer_register.html"
    form_class = ProducerRegisterForm
    success_url = reverse_lazy("core:dashboard")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Producer account created. You can now list products and manage orders.")
        return super().form_valid(form)


class ProducerDashboardView(ProducerAccessMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sync_producer_settlements(self.producer)

        recent_products = list(
            Product.objects.filter(producer=self.producer).order_by("-updated_at")[:5]
        )
        low_stock_products = list(
            Product.objects.filter(producer=self.producer, is_active=True, stock_quantity__lte=5)
            .exclude(stock_quantity=0)
            .order_by("stock_quantity", "name")[:5]
        )
        incoming_items = list(
            OrderItem.objects.filter(product__producer=self.producer)
            .exclude(status__in=[OrderItem.STATUS_FULFILLED, OrderItem.STATUS_CANCELLED])
            .select_related("product", "order")
            .order_by("order__fulfilment_date", "order__created_at")[:6]
        )
        for item in incoming_items:
            item.food_miles = item_food_miles(item)
            item.lead_time_warning = order_item_requires_attention(item)

        active_surplus = list(
            SurplusListing.objects.filter(producer=self.producer, is_active=True)
            .select_related("product")
            .order_by("available_until")[:4]
        )
        recent_content = list(
            ProducerContent.objects.filter(producer=self.producer)
            .select_related("product")
            .order_by("-updated_at")[:4]
        )
        pending_settlements = list(
            ProducerSettlement.objects.filter(producer=self.producer, status=ProducerSettlement.STATUS_PENDING)
            .order_by("-week_start")[:4]
        )

        context.update(
            {
                "producer": self.producer,
                "recent_products": recent_products,
                "low_stock_products": low_stock_products,
                "incoming_items": incoming_items,
                "urgent_items": [item for item in incoming_items if item.lead_time_warning],
                "active_surplus": active_surplus,
                "recent_content": recent_content,
                "pending_settlements": pending_settlements,
                "product_count": Product.objects.filter(producer=self.producer).count(),
                "active_product_count": Product.objects.filter(producer=self.producer, is_active=True).count(),
                "incoming_order_count": Order.objects.filter(items__product__producer=self.producer).distinct().count(),
                "surplus_count": SurplusListing.objects.filter(producer=self.producer, is_active=True).count(),
                "content_count": ProducerContent.objects.filter(producer=self.producer, is_published=True).count(),
            }
        )
        return context


class ProducerProfileUpdateView(ProducerAccessMixin, UpdateView):
    model = Producer
    form_class = ProducerProfileForm
    template_name = "core/producer_profile_form.html"
    success_url = reverse_lazy("core:dashboard")

    def get_object(self, queryset=None):
        return self.producer

    def form_valid(self, form):
        messages.success(self.request, "Producer profile updated.")
        return super().form_valid(form)


class ProductOwnerQuerysetMixin(ProducerAccessMixin):
    def get_queryset(self):
        return Product.objects.filter(producer=self.producer).select_related("category")


class ProductListView(ProductOwnerQuerysetMixin, ListView):
    model = Product
    template_name = "core/product_list.html"
    context_object_name = "products"

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get("q", "").strip()
        visibility = self.request.GET.get("visibility", "")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(farm_origin__icontains=search)
                | Q(seasonal_highlight__icontains=search)
            )
        if visibility == "active":
            queryset = queryset.filter(is_active=True)
        elif visibility == "inactive":
            queryset = queryset.filter(is_active=False)
        elif visibility == "low-stock":
            queryset = queryset.filter(is_active=True, stock_quantity__lte=5).exclude(stock_quantity=0)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        products = self.get_queryset()
        context.update(
            {
                "search_query": self.request.GET.get("q", "").strip(),
                "visibility": self.request.GET.get("visibility", ""),
                "active_count": products.filter(is_active=True).count(),
                "inactive_count": products.filter(is_active=False).count(),
                "low_stock_count": products.filter(is_active=True, stock_quantity__lte=5).exclude(stock_quantity=0).count(),
            }
        )
        return context


class ProductCreateView(ProducerAccessMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "core/product_form.html"
    success_url = reverse_lazy("core:product-list")

    def form_valid(self, form):
        form.instance.producer = self.producer
        messages.success(self.request, "Product saved.")
        return super().form_valid(form)


class ProductUpdateView(ProductOwnerQuerysetMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "core/product_form.html"
    success_url = reverse_lazy("core:product-list")

    def form_valid(self, form):
        messages.success(self.request, "Product updated.")
        return super().form_valid(form)


class ProductDeleteView(ProductOwnerQuerysetMixin, DeleteView):
    model = Product
    template_name = "core/product_confirm_delete.html"
    success_url = reverse_lazy("core:product-list")

    def form_valid(self, form):
        messages.success(self.request, "Product deleted.")
        return super().form_valid(form)


class ProducerOrderListView(ProducerAccessMixin, ListView):
    model = Order
    template_name = "core/order_list.html"
    context_object_name = "orders"

    def get_queryset(self):
        status = self.request.GET.get("status", "").strip()
        item_queryset = OrderItem.objects.filter(product__producer=self.producer).select_related("product")
        if status:
            item_queryset = item_queryset.filter(status=status)

        queryset = Order.objects.filter(items__product__producer=self.producer)
        if status:
            queryset = queryset.filter(items__status=status, items__product__producer=self.producer)

        return (
            queryset
            .distinct()
            .select_related("customer")
            .prefetch_related(Prefetch("items", queryset=item_queryset))
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for order in context["orders"]:
            order.producer_items = list(order.items.all())
            for item in order.producer_items:
                item.food_miles = item_food_miles(item)
                item.lead_time_warning = order_item_requires_attention(item)
        context["status_filter"] = self.request.GET.get("status", "").strip()
        context["item_statuses"] = OrderItem.STATUS_CHOICES
        return context


class ProducerOrderDetailView(ProducerAccessMixin, DetailView):
    model = Order
    template_name = "core/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        item_queryset = OrderItem.objects.filter(product__producer=self.producer).select_related("product")
        return (
            Order.objects.filter(items__product__producer=self.producer)
            .distinct()
            .select_related("customer")
            .prefetch_related(Prefetch("items", queryset=item_queryset))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        producer_items = list(self.object.items.all())
        for item in producer_items:
            item.food_miles = item_food_miles(item)
            item.lead_time_warning = order_item_requires_attention(item)
        context["producer_items"] = producer_items
        return context


class ProducerOrderItemUpdateView(ProducerAccessMixin, UpdateView):
    model = OrderItem
    form_class = ProducerOrderItemForm
    template_name = "core/order_item_form.html"

    def get_queryset(self):
        return OrderItem.objects.filter(product__producer=self.producer).select_related("order", "product")

    def get_success_url(self):
        return reverse("core:order-detail", kwargs={"pk": self.object.order_id})

    def form_valid(self, form):
        messages.success(self.request, "Order item updated.")
        return super().form_valid(form)


class ProducerSettlementListView(ProducerAccessMixin, ListView):
    model = ProducerSettlement
    template_name = "core/settlement_list.html"
    context_object_name = "settlements"

    def get_queryset(self):
        sync_producer_settlements(self.producer)
        return ProducerSettlement.objects.filter(producer=self.producer).order_by("-week_start")


class ProducerSettlementDetailView(ProducerAccessMixin, DetailView):
    model = ProducerSettlement
    template_name = "core/settlement_detail.html"
    context_object_name = "settlement"

    def get_queryset(self):
        sync_producer_settlements(self.producer)
        return ProducerSettlement.objects.filter(producer=self.producer).prefetch_related(
            "entries__order_item__product",
            "entries__order_item__order",
        )


class ProducerSurplusListView(ProducerAccessMixin, ListView):
    model = SurplusListing
    template_name = "core/surplus_list.html"
    context_object_name = "surplus_listings"

    def get_queryset(self):
        return SurplusListing.objects.filter(producer=self.producer).select_related("product")


class ProducerSurplusCreateView(ProducerAccessMixin, ProducerOwnedFormMixin, CreateView):
    model = SurplusListing
    form_class = SurplusListingForm
    template_name = "core/surplus_form.html"
    success_url = reverse_lazy("core:surplus-list")

    def form_valid(self, form):
        form.instance.producer = self.producer
        messages.success(self.request, "Surplus listing published.")
        return super().form_valid(form)


class ProducerSurplusUpdateView(ProducerAccessMixin, ProducerOwnedFormMixin, UpdateView):
    model = SurplusListing
    form_class = SurplusListingForm
    template_name = "core/surplus_form.html"
    success_url = reverse_lazy("core:surplus-list")

    def get_queryset(self):
        return SurplusListing.objects.filter(producer=self.producer).select_related("product")

    def form_valid(self, form):
        messages.success(self.request, "Surplus listing updated.")
        return super().form_valid(form)


class ProducerSurplusDeleteView(ProducerAccessMixin, DeleteView):
    model = SurplusListing
    template_name = "core/surplus_confirm_delete.html"
    success_url = reverse_lazy("core:surplus-list")

    def get_queryset(self):
        return SurplusListing.objects.filter(producer=self.producer).select_related("product")

    def form_valid(self, form):
        messages.success(self.request, "Surplus listing removed.")
        return super().form_valid(form)


class ProducerContentListView(ProducerAccessMixin, ListView):
    model = ProducerContent
    template_name = "core/content_list.html"
    context_object_name = "content_items"

    def get_queryset(self):
        return ProducerContent.objects.filter(producer=self.producer).select_related("product")


class ProducerContentCreateView(ProducerAccessMixin, ProducerOwnedFormMixin, CreateView):
    model = ProducerContent
    form_class = ProducerContentForm
    template_name = "core/content_form.html"
    success_url = reverse_lazy("core:content-list")

    def form_valid(self, form):
        form.instance.producer = self.producer
        messages.success(self.request, "Producer content saved.")
        return super().form_valid(form)


class ProducerContentUpdateView(ProducerAccessMixin, ProducerOwnedFormMixin, UpdateView):
    model = ProducerContent
    form_class = ProducerContentForm
    template_name = "core/content_form.html"
    success_url = reverse_lazy("core:content-list")

    def get_queryset(self):
        return ProducerContent.objects.filter(producer=self.producer).select_related("product")

    def form_valid(self, form):
        messages.success(self.request, "Producer content updated.")
        return super().form_valid(form)


class ProducerContentDeleteView(ProducerAccessMixin, DeleteView):
    model = ProducerContent
    template_name = "core/content_confirm_delete.html"
    success_url = reverse_lazy("core:content-list")

    def get_queryset(self):
        return ProducerContent.objects.filter(producer=self.producer).select_related("product")

    def form_valid(self, form):
        messages.success(self.request, "Producer content deleted.")
        return super().form_valid(form)
