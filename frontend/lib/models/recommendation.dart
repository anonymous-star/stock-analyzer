class RecommendedStock {
  final String ticker;
  final String name;
  final double? currentPrice;
  final double? changePercent;
  final String? currency;
  final String recommendation; // BUY / HOLD / SELL
  final int score;
  final List<String> reasons;
  final double? rsi;
  final String? maTrend;

  RecommendedStock({
    required this.ticker,
    required this.name,
    this.currentPrice,
    this.changePercent,
    this.currency,
    required this.recommendation,
    required this.score,
    required this.reasons,
    this.rsi,
    this.maTrend,
  });

  factory RecommendedStock.fromJson(Map<String, dynamic> json) {
    return RecommendedStock(
      ticker: json['ticker'] ?? '',
      name: json['name'] ?? '',
      currentPrice: (json['current_price'] as num?)?.toDouble(),
      changePercent: (json['change_percent'] as num?)?.toDouble(),
      currency: json['currency'],
      recommendation: json['recommendation'] ?? 'HOLD',
      score: (json['score'] as num?)?.toInt() ?? 0,
      reasons: List<String>.from(json['reasons'] ?? []),
      rsi: (json['rsi'] as num?)?.toDouble(),
      maTrend: json['ma_trend'],
    );
  }

  bool get isBuy => recommendation == 'BUY';
  bool get isSell => recommendation == 'SELL';
}
