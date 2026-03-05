import 'package:flutter/material.dart';
import '../models/stock.dart';

class IndicatorWidget extends StatelessWidget {
  final TechnicalData data;

  const IndicatorWidget({super.key, required this.data});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Text('기술적 지표', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        ),

        // Moving Averages
        _buildSection('이동평균선', [
          _buildRow('MA20', data.ma20, _maColor(data.currentPrice, data.ma20)),
          _buildRow('MA50', data.ma50, _maColor(data.currentPrice, data.ma50)),
          _buildRow('MA200', data.ma200, _maColor(data.currentPrice, data.ma200)),
        ]),

        // RSI
        if (data.rsi != null) _buildRsiCard(data.rsi!),

        // MACD
        if (data.macd != null) _buildMacdCard(data.macd!),

        // Bollinger Bands
        if (data.bollingerBands != null) _buildBBCard(data.bollingerBands!),

        // Signals
        if (data.signals != null && data.signals!.isNotEmpty) _buildSignalsCard(data.signals!),
      ],
    );
  }

  Widget _buildSection(String title, List<Widget> rows) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            const SizedBox(height: 8),
            ...rows,
          ],
        ),
      ),
    );
  }

  Widget _buildRow(String label, double? value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 13)),
          Text(
            value != null ? _formatNum(value) : '--',
            style: TextStyle(fontSize: 13, color: color, fontWeight: FontWeight.w500),
          ),
        ],
      ),
    );
  }

  Widget _buildRsiCard(double rsi) {
    Color rsiColor;
    String rsiLabel;
    if (rsi > 70) {
      rsiColor = Colors.red;
      rsiLabel = '과매수';
    } else if (rsi < 30) {
      rsiColor = Colors.blue;
      rsiLabel = '과매도';
    } else {
      rsiColor = Colors.green;
      rsiLabel = '중립';
    }

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('RSI (14)', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: rsiColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(rsiLabel, style: TextStyle(color: rsiColor, fontSize: 12, fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: LinearProgressIndicator(
                    value: rsi / 100,
                    backgroundColor: Colors.grey[200],
                    valueColor: AlwaysStoppedAnimation<Color>(rsiColor),
                    minHeight: 8,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
                const SizedBox(width: 12),
                Text(rsi.toStringAsFixed(1), style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: rsiColor)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMacdCard(MacdData macd) {
    final histColor = (macd.histogram ?? 0) > 0 ? Colors.red : Colors.blue;
    return _buildSection('MACD (12/26/9)', [
      _buildRow('MACD', macd.macd, Colors.orange),
      _buildRow('Signal', macd.signal, Colors.purple),
      _buildRow('Histogram', macd.histogram, histColor),
    ]);
  }

  Widget _buildBBCard(BollingerBands bb) {
    return _buildSection('볼린저밴드 (20, 2σ)', [
      _buildRow('상단', bb.upper, Colors.red),
      _buildRow('중단', bb.mid, Colors.grey),
      _buildRow('하단', bb.lower, Colors.blue),
    ]);
  }

  Widget _buildSignalsCard(Map<String, String> signals) {
    final signalLabels = {
      'ma_trend': 'MA 추세',
      'rsi_signal': 'RSI',
      'macd_signal': 'MACD',
      'bb_position': '볼린저밴드',
    };
    final signalColors = {
      'bullish': Colors.red,
      'bearish': Colors.blue,
      'neutral': Colors.grey,
      'overbought': Colors.red,
      'oversold': Colors.blue,
      'above_upper': Colors.red,
      'below_lower': Colors.blue,
      'upper_half': Colors.orange,
      'lower_half': Colors.cyan,
    };
    final signalTranslations = {
      'bullish': '상승',
      'bearish': '하락',
      'neutral': '중립',
      'overbought': '과매수',
      'oversold': '과매도',
      'above_upper': '상단 돌파',
      'below_lower': '하단 이탈',
      'upper_half': '상단부',
      'lower_half': '하단부',
    };

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('신호 종합', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: signals.entries.map((e) {
                final label = signalLabels[e.key] ?? e.key;
                final color = signalColors[e.value] ?? Colors.grey;
                final translation = signalTranslations[e.value] ?? e.value;
                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: color.withOpacity(0.3)),
                  ),
                  child: Text(
                    '$label: $translation',
                    style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w500),
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Color _maColor(double? price, double? ma) {
    if (price == null || ma == null) return Colors.grey;
    return price > ma ? Colors.red : Colors.blue;
  }

  String _formatNum(double value) {
    if (value.abs() >= 1000) {
      return value.toStringAsFixed(0).replaceAllMapped(
        RegExp(r'\B(?=(\d{3})+(?!\d))'),
        (m) => ',',
      );
    }
    return value.toStringAsFixed(4);
  }
}
