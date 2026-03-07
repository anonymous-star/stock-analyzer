class ScoreBreakdown {
  final int technical;
  final int financial;
  final int volume;
  final int momentum;
  final int news;

  ScoreBreakdown({
    this.technical = 0,
    this.financial = 0,
    this.volume = 0,
    this.momentum = 0,
    this.news = 0,
  });

  factory ScoreBreakdown.fromJson(Map<String, dynamic> json) {
    return ScoreBreakdown(
      technical: (json['technical'] as num?)?.toInt() ?? 0,
      financial: (json['financial'] as num?)?.toInt() ?? 0,
      volume: (json['volume'] as num?)?.toInt() ?? 0,
      momentum: (json['momentum'] as num?)?.toInt() ?? 0,
      news: (json['news'] as num?)?.toInt() ?? 0,
    );
  }
}

class RecommendedStock {
  final String ticker;
  final String name;
  final double? currentPrice;
  final double? changePercent;
  final String? currency;
  final String recommendation; // BUY / HOLD / SELL
  final int score;
  final int maxScore;
  final ScoreBreakdown? scoreBreakdown;
  final List<String> reasons;
  final double? rsi;
  final String? maTrend;
  final int confidence; // 확신도 (30-95%)
  final double? peRatio;
  final double? volumeRatio;

  RecommendedStock({
    required this.ticker,
    required this.name,
    this.currentPrice,
    this.changePercent,
    this.currency,
    required this.recommendation,
    required this.score,
    this.maxScore = 24,
    this.confidence = 50,
    this.scoreBreakdown,
    required this.reasons,
    this.rsi,
    this.maTrend,
    this.peRatio,
    this.volumeRatio,
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
      maxScore: (json['max_score'] as num?)?.toInt() ?? 24,
      confidence: (json['confidence'] as num?)?.toInt() ?? 50,
      scoreBreakdown: json['score_breakdown'] != null
          ? ScoreBreakdown.fromJson(json['score_breakdown'])
          : null,
      reasons: List<String>.from(json['reasons'] ?? []),
      rsi: (json['rsi'] as num?)?.toDouble(),
      maTrend: json['ma_trend'],
      peRatio: (json['pe_ratio'] as num?)?.toDouble(),
      volumeRatio: (json['volume_ratio'] as num?)?.toDouble(),
    );
  }

  bool get isBuy => recommendation == 'BUY';
  bool get isSell => recommendation == 'SELL';
}
