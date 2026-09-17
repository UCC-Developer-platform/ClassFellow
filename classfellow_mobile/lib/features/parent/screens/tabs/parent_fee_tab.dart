import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_endpoints.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../models/parent_models.dart';

class ParentFeeTab extends StatefulWidget {
  final int enrollmentId;

  const ParentFeeTab({super.key, required this.enrollmentId});

  @override
  State<ParentFeeTab> createState() => _ParentFeeTabState();
}

class _ParentFeeTabState extends State<ParentFeeTab> {
  bool _isLoading = true;
  String? _errorMessage;
  FeeSummaryResponse? _feeSummary;

  @override
  void initState() {
    super.initState();
    _fetchFees();
  }

  @override
  void didUpdateWidget(covariant ParentFeeTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.enrollmentId != widget.enrollmentId) {
      _fetchFees();
    }
  }

  Future<void> _fetchFees() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final apiClient = context.read<ApiClient>();
    try {
      final response = await apiClient.get(
        ApiEndpoints.parentFees,
        queryParams: {'enrollment_id': widget.enrollmentId.toString()},
      );

      if (response is Map<String, dynamic>) {
        setState(() {
          _feeSummary = FeeSummaryResponse.fromJson(response);
          _isLoading = false;
        });
      } else {
        setState(() {
          _errorMessage = 'Invalid fee response format.';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.emerald500));
    }

    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.rose500),
              const SizedBox(height: 12),
              Text(_errorMessage!, textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.textSecondary)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _fetchFees,
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.emerald500),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_feeSummary == null) {
      return const Center(child: Text('No fee information available.', style: TextStyle(color: AppTheme.textMuted)));
    }

    final summary = _feeSummary!;

    return RefreshIndicator(
      onRefresh: _fetchFees,
      color: AppTheme.emerald500,
      backgroundColor: AppTheme.cardBackground,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 3-Metric Financial Cards
          Row(
            children: [
              Expanded(
                child: _buildMetricCard(
                  title: 'Billed',
                  amount: 'Rs. ${summary.totalBilled.toStringAsFixed(0)}',
                  color: Colors.blueAccent,
                  icon: Icons.receipt_long_rounded,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildMetricCard(
                  title: 'Paid',
                  amount: 'Rs. ${summary.totalPaid.toStringAsFixed(0)}',
                  color: AppTheme.emerald500,
                  icon: Icons.check_circle_outline_rounded,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildMetricCard(
                  title: 'Balance',
                  amount: 'Rs. ${summary.totalOutstanding.toStringAsFixed(0)}',
                  color: summary.totalOutstanding > 0 ? AppTheme.rose500 : AppTheme.emerald500,
                  icon: Icons.account_balance_wallet_outlined,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Invoices Section
          const Text(
            'Fee Invoices',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 10),
          if (summary.invoices.isEmpty)
            _buildEmptyCard('No invoices generated yet.')
          else
            ...summary.invoices.map((inv) => _buildInvoiceTile(inv)),

          const SizedBox(height: 24),

          // Payment Receipts Section
          const Text(
            'Payment Receipts',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 10),
          if (summary.payments.isEmpty)
            _buildEmptyCard('No payment history recorded.')
          else
            ...summary.payments.map((pmt) => _buildPaymentTile(pmt)),
        ],
      ),
    );
  }

  Widget _buildMetricCard({
    required String title,
    required String amount,
    required Color color,
    required IconData icon,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 4),
              Text(
                title,
                style: const TextStyle(fontSize: 11, color: AppTheme.textMuted, fontWeight: FontWeight.w500),
              ),
            ],
          ),
          const SizedBox(height: 8),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              amount,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInvoiceTile(FeeInvoiceRecord invoice) {
    Color statusColor = AppTheme.textMuted;
    if (invoice.status == 'PAID') {
      statusColor = AppTheme.emerald500;
    } else if (invoice.status == 'PARTIAL') {
      statusColor = AppTheme.amber500;
    } else if (invoice.status == 'ISSUED' || invoice.status == 'OVERDUE') {
      statusColor = AppTheme.rose500;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.cardBackground,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: statusColor.withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(Icons.description_outlined, color: statusColor, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${invoice.monthYear} Fee Invoice',
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Due: ${invoice.dueDate}',
                  style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                'Rs. ${invoice.totalAmount.toStringAsFixed(0)}',
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 2),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  invoice.status,
                  style: TextStyle(
                    color: statusColor,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPaymentTile(PaymentReceiptRecord pmt) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.cardBackground,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: AppTheme.emerald500.withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.receipt_rounded, color: AppTheme.emerald500, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Receipt #${pmt.receiptNumber}',
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${pmt.paymentDate} • ${pmt.paymentMethod}',
                  style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                ),
              ],
            ),
          ),
          Text(
            'Rs. ${pmt.amountPaid.toStringAsFixed(0)}',
            style: const TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 14,
              color: AppTheme.emerald500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyCard(String message) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
      decoration: BoxDecoration(
        color: AppTheme.cardBackground,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      alignment: Alignment.center,
      child: Text(message, style: const TextStyle(color: AppTheme.textMuted, fontSize: 13)),
    );
  }
}
