"""
Admin financial reporting views for the Bristol Regional Food Network.

Provides the network administrator with tools to monitor the 5 %
commission, view per-order financial breakdowns, generate date-range
reports, and export data as CSV for accounting software.

Test-case coverage
------------------
TC-025  – commission monitoring, financial accuracy, report generation
"""

import csv
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView, TemplateView

from .models import (
    Order,
    OrderItem,
    Payment,
    Producer,
    ProducerSettlement,
    TraceabilityRecord,
)
from .services import COMMISSION_RATE, TWOPLACES


@method_decorator(staff_member_required, name="dispatch")
class AdminFinancialDashboardView(TemplateView):
    """
    Top-level financial dashboard for the network administrator.

    Shows summary statistics: total revenue, total commission earned,
    total paid to producers, number of orders processed, and
    outstanding settlements.
    """

    template_name = "core/admin_financial_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Date range filtering
        date_from = self.request.GET.get("from", "")
        date_to = self.request.GET.get("to", "")

        payments = Payment.objects.all()

        if date_from:
            payments = payments.filter(created_at__date__gte=date_from)
        if date_to:
            payments = payments.filter(created_at__date__lte=date_to)

        aggregates = payments.aggregate(
            total_revenue=Sum("total_amount"),
            total_commission=Sum("network_commission"),
            total_producer_pay=Sum("producer_amount"),
            order_count=Count("id"),
        )

        # Year-to-date totals
        year_start = timezone.now().replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        ytd = Payment.objects.filter(created_at__gte=year_start).aggregate(
            ytd_revenue=Sum("total_amount"),
            ytd_commission=Sum("network_commission"),
        )

        # Outstanding settlements
        pending_settlements = ProducerSettlement.objects.filter(
            status=ProducerSettlement.STATUS_PENDING
        ).aggregate(
            pending_count=Count("id"),
            pending_amount=Sum("net_amount"),
        )

        context.update({
            "total_revenue": aggregates["total_revenue"] or Decimal("0.00"),
            "total_commission": aggregates["total_commission"] or Decimal("0.00"),
            "total_producer_pay": aggregates["total_producer_pay"] or Decimal("0.00"),
            "order_count": aggregates["order_count"] or 0,
            "ytd_revenue": ytd["ytd_revenue"] or Decimal("0.00"),
            "ytd_commission": ytd["ytd_commission"] or Decimal("0.00"),
            "pending_settlement_count": pending_settlements["pending_count"] or 0,
            "pending_settlement_amount": pending_settlements["pending_amount"] or Decimal("0.00"),
            "date_from": date_from,
            "date_to": date_to,
        })
        return context


@method_decorator(staff_member_required, name="dispatch")
class AdminCommissionReportView(ListView):
    """
    Detailed commission report with per-order breakdown.

    Supports date-range filtering and links through to individual
    order financial details.  Maps directly to TC-025 acceptance
    criteria for commission monitoring.
    """

    template_name = "core/admin_commission_report.html"
    context_object_name = "payments"
    paginate_by = 25

    def get_queryset(self):
        qs = Payment.objects.select_related("order__customer").order_by(
            "-created_at"
        )
        date_from = self.request.GET.get("from", "")
        date_to = self.request.GET.get("to", "")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        totals = qs.aggregate(
            total_revenue=Sum("total_amount"),
            total_commission=Sum("network_commission"),
            total_producer=Sum("producer_amount"),
        )
        context.update({
            "total_revenue": totals["total_revenue"] or Decimal("0.00"),
            "total_commission": totals["total_commission"] or Decimal("0.00"),
            "total_producer": totals["total_producer"] or Decimal("0.00"),
            "date_from": self.request.GET.get("from", ""),
            "date_to": self.request.GET.get("to", ""),
        })
        return context


@method_decorator(staff_member_required, name="dispatch")
class AdminOrderFinancialDetailView(DetailView):
    """
    Detailed financial view for a single order.

    Shows the full itemised breakdown with per-producer commission
    split.  For multi-vendor orders (TC-008), each producer's share
    is calculated individually.
    """

    model = Order
    template_name = "core/admin_order_financial_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return Order.objects.select_related("customer").prefetch_related(
            "items__product__producer",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object

        # Per-producer breakdown
        producer_data = {}
        items = order.items.select_related("product__producer").all()

        for item in items:
            producer = item.product.producer
            pid = producer.pk
            if pid not in producer_data:
                producer_data[pid] = {
                    "producer": producer,
                    "items": [],
                    "subtotal": Decimal("0.00"),
                }
            line_total = (item.price * item.quantity).quantize(
                TWOPLACES, rounding=ROUND_HALF_UP
            )
            producer_data[pid]["items"].append({
                "item": item,
                "line_total": line_total,
            })
            producer_data[pid]["subtotal"] += line_total

        # Calculate commission per producer
        for data in producer_data.values():
            data["commission"] = (
                data["subtotal"] * COMMISSION_RATE
            ).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            data["net"] = (
                data["subtotal"] - data["commission"]
            ).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        # Payment record
        try:
            payment = order.payment
        except Payment.DoesNotExist:
            payment = None

        context.update({
            "producer_breakdown": list(producer_data.values()),
            "payment": payment,
        })
        return context


@method_decorator(staff_member_required, name="dispatch")
class AdminSettlementOverviewView(ListView):
    """
    Overview of all producer settlements for the administrator.

    Shows weekly settlement periods with totals, status, and links
    to individual settlement details.
    """

    template_name = "core/admin_settlement_overview.html"
    context_object_name = "settlements"
    paginate_by = 20

    def get_queryset(self):
        qs = ProducerSettlement.objects.select_related("producer").order_by(
            "-week_start"
        )
        status = self.request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_filter"] = self.request.GET.get("status", "")
        context["status_choices"] = ProducerSettlement.STATUS_CHOICES
        totals = self.get_queryset().aggregate(
            total_gross=Sum("gross_amount"),
            total_commission=Sum("commission_amount"),
            total_net=Sum("net_amount"),
        )
        context.update({
            "total_gross": totals["total_gross"] or Decimal("0.00"),
            "total_commission": totals["total_commission"] or Decimal("0.00"),
            "total_net": totals["total_net"] or Decimal("0.00"),
        })
        return context


@method_decorator(staff_member_required, name="dispatch")
class AdminTraceabilityReportView(ListView):
    """
    Traceability report showing the full audit trail of products
    sold: producer, customer, allergens, food miles, dates.

    Supports filtering by producer, date range, and allergen keyword.
    """

    template_name = "core/admin_traceability_report.html"
    context_object_name = "records"
    paginate_by = 30

    def get_queryset(self):
        qs = TraceabilityRecord.objects.select_related(
            "producer", "customer", "order_item__order"
        ).order_by("-created_at")

        producer_id = self.request.GET.get("producer", "")
        date_from = self.request.GET.get("from", "")
        date_to = self.request.GET.get("to", "")
        allergen = self.request.GET.get("allergen", "").strip()

        if producer_id:
            qs = qs.filter(producer_id=producer_id)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        if allergen:
            qs = qs.filter(allergen_info_snapshot__icontains=allergen)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["producers"] = Producer.objects.order_by("business_name")
        context["producer_filter"] = self.request.GET.get("producer", "")
        context["date_from"] = self.request.GET.get("from", "")
        context["date_to"] = self.request.GET.get("to", "")
        context["allergen_filter"] = self.request.GET.get("allergen", "")
        return context


# ---------------------------------------------------------------------------
# CSV export views
# ---------------------------------------------------------------------------

@staff_member_required
def export_commission_csv(request):
    """
    Export commission report as CSV (TC-025 acceptance criteria:
    reports exportable in CSV format for accounting software).
    """
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")

    payments = Payment.objects.select_related("order__customer").order_by(
        "-created_at"
    )
    if date_from:
        payments = payments.filter(created_at__date__gte=date_from)
    if date_to:
        payments = payments.filter(created_at__date__lte=date_to)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="brfn_commission_report.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        "Order Reference",
        "Date",
        "Customer",
        "Total Amount (£)",
        "Network Commission 5% (£)",
        "Producer Amount 95% (£)",
    ])

    for payment in payments:
        order = payment.order
        writer.writerow([
            order.reference or f"ORD-{order.pk:05d}",
            payment.created_at.strftime("%Y-%m-%d %H:%M"),
            order.customer_display_name,
            f"{payment.total_amount:.2f}",
            f"{payment.network_commission:.2f}",
            f"{payment.producer_amount:.2f}",
        ])

    return response


@staff_member_required
def export_traceability_csv(request):
    """
    Export traceability records as CSV for food-safety auditing.
    """
    qs = TraceabilityRecord.objects.select_related(
        "producer", "customer", "order_item__order"
    ).order_by("-created_at")

    producer_id = request.GET.get("producer", "")
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")

    if producer_id:
        qs = qs.filter(producer_id=producer_id)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="brfn_traceability_report.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        "Order Reference",
        "Date",
        "Product",
        "Category",
        "Producer",
        "Producer Postcode",
        "Customer Postcode",
        "Food Miles",
        "Allergens",
        "Organic",
        "Harvest Date",
        "Best Before",
        "Quantity",
        "Unit Price (£)",
        "Line Total (£)",
    ])

    for record in qs:
        writer.writerow([
            record.order_reference,
            record.created_at.strftime("%Y-%m-%d %H:%M"),
            record.product_name_snapshot,
            record.product_category_snapshot,
            record.producer_name_snapshot,
            record.producer_postcode_snapshot,
            record.customer_postcode_snapshot,
            f"{record.food_miles:.1f}",
            record.allergen_info_snapshot or "None",
            "Yes" if record.organic_certified else "No",
            record.harvest_date.strftime("%Y-%m-%d") if record.harvest_date else "",
            record.best_before_date.strftime("%Y-%m-%d") if record.best_before_date else "",
            record.quantity,
            f"{record.unit_price:.2f}",
            f"{record.line_total:.2f}",
        ])

    return response
