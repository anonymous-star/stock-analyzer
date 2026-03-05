import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../models/stock.dart';

class TechnicalChart extends StatelessWidget {
  final List<PricePoint> data;
  final String? period;

  const TechnicalChart({super.key, required this.data, this.period});

  @override
  Widget build(BuildContext context) {
    if (data.isEmpty) {
      return const Center(child: Text('차트 데이터 없음'));
    }

    final closes = data.map((e) => e.close).toList();
    final minY = closes.reduce((a, b) => a < b ? a : b) * 0.98;
    final maxY = closes.reduce((a, b) => a > b ? a : b) * 1.02;
    final isUp = closes.last >= closes.first;
    final lineColor = isUp ? Colors.red : Colors.blue;

    final spots = data.asMap().entries.map((e) {
      return FlSpot(e.key.toDouble(), e.value.close);
    }).toList();

    // Show fewer x-axis labels to avoid crowding
    final step = (data.length / 5).ceil().clamp(1, data.length);

    return LineChart(
      LineChartData(
        minY: minY,
        maxY: maxY,
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: (maxY - minY) / 4,
          getDrawingHorizontalLine: (_) => FlLine(
            color: Colors.grey.withOpacity(0.2),
            strokeWidth: 1,
          ),
        ),
        borderData: FlBorderData(show: false),
        titlesData: FlTitlesData(
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 60,
              getTitlesWidget: (value, meta) {
                return Text(
                  _formatPrice(value),
                  style: const TextStyle(fontSize: 10, color: Colors.grey),
                );
              },
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 22,
              interval: step.toDouble(),
              getTitlesWidget: (value, meta) {
                final idx = value.toInt();
                if (idx < 0 || idx >= data.length) return const SizedBox.shrink();
                final date = data[idx].date;
                final parts = date.split('-');
                return Text(
                  '${parts[1]}/${parts[2]}',
                  style: const TextStyle(fontSize: 9, color: Colors.grey),
                );
              },
            ),
          ),
          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
        lineTouchData: LineTouchData(
          touchTooltipData: LineTouchTooltipData(
            getTooltipColor: (_) => Colors.black87,
            getTooltipItems: (touchedSpots) {
              return touchedSpots.map((spot) {
                final idx = spot.x.toInt();
                if (idx < 0 || idx >= data.length) return null;
                return LineTooltipItem(
                  '${data[idx].date}\n${_formatPrice(spot.y)}',
                  const TextStyle(color: Colors.white, fontSize: 12),
                );
              }).toList();
            },
          ),
        ),
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            curveSmoothness: 0.3,
            color: lineColor,
            barWidth: 2,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(
              show: true,
              color: lineColor.withOpacity(0.1),
            ),
          ),
        ],
      ),
    );
  }

  String _formatPrice(double value) {
    if (value >= 10000) {
      return '${(value / 1000).toStringAsFixed(0)}K';
    }
    return value.toStringAsFixed(2);
  }
}
