class StockQuote {
  final String ticker;
  final String? name;
  final double? currentPrice;
  final double? previousClose;
  final double? change;
  final double? changePercent;
  final int? volume;
  final double? marketCap;
  final String? currency;
  final double? weekHigh52;
  final double? weekLow52;

  StockQuote({
    required this.ticker,
    this.name,
    this.currentPrice,
    this.previousClose,
    this.change,
    this.changePercent,
    this.volume,
    this.marketCap,
    this.currency,
    this.weekHigh52,
    this.weekLow52,
  });

  factory StockQuote.fromJson(Map<String, dynamic> json) {
    return StockQuote(
      ticker: json['ticker'] ?? '',
      name: json['name'],
      currentPrice: (json['current_price'] as num?)?.toDouble(),
      previousClose: (json['previous_close'] as num?)?.toDouble(),
      change: (json['change'] as num?)?.toDouble(),
      changePercent: (json['change_percent'] as num?)?.toDouble(),
      volume: json['volume'] as int?,
      marketCap: (json['market_cap'] as num?)?.toDouble(),
      currency: json['currency'],
      weekHigh52: (json['52_week_high'] as num?)?.toDouble(),
      weekLow52: (json['52_week_low'] as num?)?.toDouble(),
    );
  }

  bool get isUp => (changePercent ?? 0) >= 0;
}

class TechnicalData {
  final String ticker;
  final String? lastUpdated;
  final double? currentPrice;
  final double? ma20;
  final double? ma50;
  final double? ma200;
  final double? rsi;
  final MacdData? macd;
  final BollingerBands? bollingerBands;
  final double? volumeMa20;
  final int? currentVolume;
  final Map<String, String>? signals;

  TechnicalData({
    required this.ticker,
    this.lastUpdated,
    this.currentPrice,
    this.ma20,
    this.ma50,
    this.ma200,
    this.rsi,
    this.macd,
    this.bollingerBands,
    this.volumeMa20,
    this.currentVolume,
    this.signals,
  });

  factory TechnicalData.fromJson(Map<String, dynamic> json) {
    return TechnicalData(
      ticker: json['ticker'] ?? '',
      lastUpdated: json['last_updated'],
      currentPrice: (json['current_price'] as num?)?.toDouble(),
      ma20: (json['ma20'] as num?)?.toDouble(),
      ma50: (json['ma50'] as num?)?.toDouble(),
      ma200: (json['ma200'] as num?)?.toDouble(),
      rsi: (json['rsi'] as num?)?.toDouble(),
      macd: json['macd'] != null ? MacdData.fromJson(json['macd']) : null,
      bollingerBands: json['bollinger_bands'] != null
          ? BollingerBands.fromJson(json['bollinger_bands'])
          : null,
      volumeMa20: (json['volume_ma20'] as num?)?.toDouble(),
      currentVolume: json['current_volume'] as int?,
      signals: json['signals'] != null
          ? Map<String, String>.from(json['signals'])
          : null,
    );
  }
}

class MacdData {
  final double? macd;
  final double? signal;
  final double? histogram;

  MacdData({this.macd, this.signal, this.histogram});

  factory MacdData.fromJson(Map<String, dynamic> json) {
    return MacdData(
      macd: (json['macd'] as num?)?.toDouble(),
      signal: (json['signal'] as num?)?.toDouble(),
      histogram: (json['histogram'] as num?)?.toDouble(),
    );
  }
}

class BollingerBands {
  final double? upper;
  final double? mid;
  final double? lower;

  BollingerBands({this.upper, this.mid, this.lower});

  factory BollingerBands.fromJson(Map<String, dynamic> json) {
    return BollingerBands(
      upper: (json['upper'] as num?)?.toDouble(),
      mid: (json['mid'] as num?)?.toDouble(),
      lower: (json['lower'] as num?)?.toDouble(),
    );
  }
}

class PricePoint {
  final String date;
  final double open;
  final double high;
  final double low;
  final double close;
  final int volume;

  PricePoint({
    required this.date,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.volume,
  });

  factory PricePoint.fromJson(Map<String, dynamic> json) {
    return PricePoint(
      date: json['date'] ?? '',
      open: (json['open'] as num).toDouble(),
      high: (json['high'] as num).toDouble(),
      low: (json['low'] as num).toDouble(),
      close: (json['close'] as num).toDouble(),
      volume: json['volume'] as int,
    );
  }
}
