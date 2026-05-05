"""
URL patterns for the admin financial reporting and traceability
views.

These should be included in the main core/urls.py with::

    path("admin-reports/", include("core.admin_urls")),

All views are protected by @staff_member_required so only Django
admin/staff users can access them.
"""

from django.urls import path

from .admin_views import (
    AdminCommissionReportView,
    AdminFinancialDashboardView,
    AdminOrderFinancialDetailView,
    AdminSettlementOverviewView,
    AdminTraceabilityReportView,
    export_commission_csv,
    export_traceability_csv,
)

app_name = "admin_reports"

urlpatterns = [
    path(
        "",
        AdminFinancialDashboardView.as_view(),
        name="financial-dashboard",
    ),
    path(
        "commission/",
        AdminCommissionReportView.as_view(),
        name="commission-report",
    ),
    path(
        "commission/export/",
        export_commission_csv,
        name="commission-export",
    ),
    path(
        "orders/<int:pk>/",
        AdminOrderFinancialDetailView.as_view(),
        name="order-financial-detail",
    ),
    path(
        "settlements/",
        AdminSettlementOverviewView.as_view(),
        name="settlement-overview",
    ),
    path(
        "traceability/",
        AdminTraceabilityReportView.as_view(),
        name="traceability-report",
    ),
    path(
        "traceability/export/",
        export_traceability_csv,
        name="traceability-export",
    ),
]
