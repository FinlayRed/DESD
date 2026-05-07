import csv

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.db.models import OuterRef, Prefetch, Q, Subquery
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from .forms import (
    CustomerLoginForm,
    CustomerProfileForm,
    CustomerRegisterForm,
    ProducerContentForm,
    ProducerLoginForm,
    ProducerOrderItemForm,
    ProducerProfileForm,
    ProducerRegisterForm,
    ProductForm,
    SurplusListingForm,
)
from .models import Category, Order, OrderItem, Producer, ProducerContent, ProducerSettlement, Product, SurplusListing
from .services import item_food_miles, order_item_requires_attention, sync_producer_settlements

# Customer browse: exclude products whose allergen_info matches any keyword in selected groups (keyword-based).
ALLERGEN_EXCLUSION_GROUPS = {
    "gluten": ["gluten", "wheat", "barley", "rye", "oat"],
    "milk": ["milk", "dairy", "lactose", "butter", "cream", "cheese", "yoghurt", "yogurt"],
    "eggs": ["egg"],
    "peanuts": ["peanut"],
    "nuts": ["almond", "hazelnut", "walnut", "cashew", "pecan", "brazil nut", "macadamia", "pistachio", "nuts"],
    "soya": ["soya", "soy"],
    "celery": ["celery"],
    "mustard": ["mustard"],
    "sesame": ["sesame"],
    "fish": ["fish"],
    "crustaceans": ["crustacean", "prawn", "shrimp", "lobster", "crab"],
    "molluscs": ["mollusc", "mussel", "oyster", "squid", "snail"],
}

ALLERGEN_EXCLUSION_CHOICES = [
    ("gluten", "Gluten"),
    ("milk", "Milk/dairy"),
    ("eggs", "Eggs"),
    ("peanuts", "Peanuts"),
    ("nuts", "Tree nuts"),
    ("soya", "Soya"),
    ("celery", "Celery"),
    ("mustard", "Mustard"),
    ("sesame", "Sesame"),
    ("fish", "Fish"),
    ("crustaceans", "Crustaceans"),
    ("molluscs", "Molluscs"),
]


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


class CustomerAccessMixin(LoginRequiredMixin):
    login_url = "/customer/login/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if Producer.objects.filter(user=request.user).exists():
            messages.error(
                request,
                "Producer accounts should manage their profile from the producer workspace.",
            )
            return redirect("core:dashboard")
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


class CustomerProfileUpdateView(CustomerAccessMixin, UpdateView):
    model = get_user_model()
    form_class = CustomerProfileForm
    template_name = "core/customer_profile_form.html"
    success_url = reverse_lazy("core:customer-profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Your profile was updated.")
        return super().form_valid(form)


class CustomerPasswordChangeView(CustomerAccessMixin, PasswordChangeView):
    template_name = "core/customer_password_change.html"
    success_url = reverse_lazy("core:customer-profile")

    def form_valid(self, form):
        messages.success(self.request, "Your password was updated.")
        return super().form_valid(form)


@require_POST
def user_logout_view(request):
    logout(request)
    return redirect("core:home")



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
    paginate_by = 10

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


class ProducerSettlementCsvExportView(ProducerSettlementDetailView):
    def get(self, request, *args, **kwargs):
        settlement = self.get_object()
        filename = f"producer_settlement_{settlement.week_start:%Y%m%d}_{settlement.week_end:%Y%m%d}.csv"

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow([
            "Settlement Week Start",
            "Settlement Week End",
            "Status",
            "Order Reference",
            "Order Date",
            "Product",
            "Quantity",
            "Unit Price (GBP)",
            "Gross Amount (GBP)",
            "Commission Amount (GBP)",
            "Net Amount (GBP)",
        ])

        for entry in settlement.entries.all():
            order_item = entry.order_item
            order = order_item.order
            writer.writerow([
                settlement.week_start.isoformat(),
                settlement.week_end.isoformat(),
                settlement.get_status_display(),
                order.reference or f"ORD-{order.pk:05d}",
                timezone.localtime(order.created_at).strftime("%Y-%m-%d %H:%M"),
                order_item.product.name,
                order_item.quantity,
                f"{order_item.price:.2f}",
                f"{entry.gross_amount:.2f}",
                f"{entry.commission_amount:.2f}",
                f"{entry.net_amount:.2f}",
            ])

        return response


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


class CustomerProductBrowseView(ListView):
    model = Product
    template_name = "core/customer_product_list.html"
    context_object_name = "products"

    UNCATEGORISED_LABEL = "Uncategorised"

    def get_queryset(self):
        active_surplus = SurplusListing.objects.filter(
            product=OuterRef("pk"),
            is_active=True,
            available_until__gte=timezone.now(),
        ).order_by("available_until")
        queryset = (
            Product.objects.filter(is_active=True)
            .annotate(
                active_surplus_discount=Subquery(active_surplus.values("discount_percent")[:1]),
                active_surplus_price=Subquery(active_surplus.values("discounted_price")[:1]),
            )
            .select_related("producer", "category")
            .order_by("name")
        )
        query = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "").strip().lower()

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(producer__business_name__icontains=query)
            )
        if category:
            queryset = queryset.filter(category__name__iexact=category)
        if self.request.GET.get("organic") == "1":
            queryset = queryset.filter(organic=True)

        exclusion_keys = [
            key
            for key in self.request.GET.getlist("exclude_allergen")
            if key in ALLERGEN_EXCLUSION_GROUPS
        ]
        if exclusion_keys:
            allergen_match = Q()
            for key in exclusion_keys:
                for kw in ALLERGEN_EXCLUSION_GROUPS[key]:
                    allergen_match |= Q(allergen_info__icontains=kw)
            queryset = queryset.exclude(allergen_match)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        products = list(context["products"])
        grouped = {}

        for product in products:
            label = product.category.name if product.category else self.UNCATEGORISED_LABEL
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
            grouped.setdefault(label, []).append(product)

        # Sort groups alphabetically; uncategorised last.
        ordered = dict(
            sorted(grouped.items(), key=lambda kv: (kv[0] == self.UNCATEGORISED_LABEL, kv[0].lower()))
        )

        context["grouped_products"] = ordered
        context["customer_browse_has_results"] = bool(products)
        if products:
            context["customer_browse_catalog_empty"] = False
        else:
            context["customer_browse_catalog_empty"] = not Product.objects.filter(is_active=True).exists()
        context["query"] = self.request.GET.get("q", "").strip()
        context["active_category"] = self.request.GET.get("category", "").strip().lower()
        context["organic_only"] = self.request.GET.get("organic") == "1"
        context["allergen_exclusion_choices"] = ALLERGEN_EXCLUSION_CHOICES
        context["active_allergen_exclusions"] = [
            key
            for key in self.request.GET.getlist("exclude_allergen")
            if key in ALLERGEN_EXCLUSION_GROUPS
        ]
        context["category_keys"] = list(
            Category.objects.order_by("name").values_list("name", flat=True)
        )
        return context


class CustomerContentListView(ListView):
    model = ProducerContent
    template_name = "core/customer_content_list.html"
    context_object_name = "content_items"

    def get_queryset(self):
        return (
            ProducerContent.objects.filter(is_published=True)
            .select_related("producer", "product")
            .order_by("-updated_at", "title")
        )


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
