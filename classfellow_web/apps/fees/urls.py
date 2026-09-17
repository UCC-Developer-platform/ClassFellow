"""
ClassFellow Web - Fees App URL Configuration
"""

from django.urls import path
from apps.fees import views

app_name = "fees"

urlpatterns = [
    path("", views.fee_workspace_view, name="workspace"),
    path("pay/", views.record_payment_view, name="record_payment"),
    path("generate/", views.generate_invoices_view, name="generate_invoices"),
    path("vouchers/<int:invoice_id>/pdf/", views.stream_fee_voucher_pdf, name="stream_voucher_pdf"),
]
