import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/stock.dart';

class StockCard extends StatelessWidget {
  final StockQuote quote;
  final VoidCallback? onTap;

  const StockCard({super.key, required this.quote, this.onTap});

  @override
  Widget build(BuildContext context) {
    final isUp = quote.isUp;
    final color = isUp ? Colors.red : Colors.blue;
    final priceStr = quote.currentPrice != null
        ? _formatPrice(quote.currentPrice!, quote.currency)
        : '--';
    final changeStr = quote.changePercent != null
        ? '${isUp ? '+' : ''}${quote.changePercent!.toStringAsFixed(2)}%'
        : '--';

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: ListTile(
        onTap: onTap,
        leading: CircleAvatar(
          backgroundColor: color.withOpacity(0.15),
          child: Text(
            (quote.ticker.split('.').first.substring(0, 1)),
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
              fontSize: 16,
            ),
          ),
        ),
        title: Row(
          children: [
            Expanded(
              child: Text(
                quote.name ?? quote.ticker,
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            Text(
              priceStr,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
            ),
          ],
        ),
        subtitle: Row(
          children: [
            Text(
              quote.ticker,
              style: TextStyle(color: Colors.grey[600], fontSize: 12),
            ),
            const Spacer(),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                changeStr,
                style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 13),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatPrice(double price, String? currency) {
    if (currency == 'KRW') {
      return NumberFormat('#,##0원').format(price.toInt());
    }
    return '\$${price.toStringAsFixed(2)}';
  }
}
