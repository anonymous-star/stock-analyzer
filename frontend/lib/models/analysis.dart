class StockAnalysis {
  final String ticker;
  final String recommendation; // BUY, HOLD, SELL
  final int confidence; // 1-5
  final double? targetPriceLow;
  final double? targetPriceHigh;
  final List<String> investmentPoints;
  final List<String> riskFactors;
  final String? technicalSummary;
  final String? fundamentalSummary;
  final String? overallSummary;

  StockAnalysis({
    required this.ticker,
    required this.recommendation,
    required this.confidence,
    this.targetPriceLow,
    this.targetPriceHigh,
    required this.investmentPoints,
    required this.riskFactors,
    this.technicalSummary,
    this.fundamentalSummary,
    this.overallSummary,
  });

  factory StockAnalysis.fromJson(Map<String, dynamic> json) {
    return StockAnalysis(
      ticker: json['ticker'] ?? '',
      recommendation: json['recommendation'] ?? 'HOLD',
      confidence: (json['confidence'] as num?)?.toInt() ?? 1,
      targetPriceLow: (json['target_price_low'] as num?)?.toDouble(),
      targetPriceHigh: (json['target_price_high'] as num?)?.toDouble(),
      investmentPoints: List<String>.from(json['investment_points'] ?? []),
      riskFactors: List<String>.from(json['risk_factors'] ?? []),
      technicalSummary: json['technical_summary'],
      fundamentalSummary: json['fundamental_summary'],
      overallSummary: json['overall_summary'],
    );
  }

  bool get isBuy => recommendation == 'BUY';
  bool get isSell => recommendation == 'SELL';
  bool get isHold => recommendation == 'HOLD';
}

class FinancialData {
  final String ticker;
  final ValuationData? valuation;
  final ProfitabilityData? profitability;
  final GrowthData? growth;
  final PerShareData? perShare;
  final CompanyInfo? companyInfo;

  FinancialData({
    required this.ticker,
    this.valuation,
    this.profitability,
    this.growth,
    this.perShare,
    this.companyInfo,
  });

  factory FinancialData.fromJson(Map<String, dynamic> json) {
    return FinancialData(
      ticker: json['ticker'] ?? '',
      valuation: json['valuation'] != null
          ? ValuationData.fromJson(json['valuation'])
          : null,
      profitability: json['profitability'] != null
          ? ProfitabilityData.fromJson(json['profitability'])
          : null,
      growth: json['growth'] != null
          ? GrowthData.fromJson(json['growth'])
          : null,
      perShare: json['per_share'] != null
          ? PerShareData.fromJson(json['per_share'])
          : null,
      companyInfo: json['company_info'] != null
          ? CompanyInfo.fromJson(json['company_info'])
          : null,
    );
  }
}

class ValuationData {
  final double? peRatio;
  final double? forwardPe;
  final double? pbRatio;
  final double? psRatio;
  final double? pegRatio;
  final double? evEbitda;

  ValuationData({
    this.peRatio,
    this.forwardPe,
    this.pbRatio,
    this.psRatio,
    this.pegRatio,
    this.evEbitda,
  });

  factory ValuationData.fromJson(Map<String, dynamic> json) {
    return ValuationData(
      peRatio: (json['pe_ratio'] as num?)?.toDouble(),
      forwardPe: (json['forward_pe'] as num?)?.toDouble(),
      pbRatio: (json['pb_ratio'] as num?)?.toDouble(),
      psRatio: (json['ps_ratio'] as num?)?.toDouble(),
      pegRatio: (json['peg_ratio'] as num?)?.toDouble(),
      evEbitda: (json['ev_ebitda'] as num?)?.toDouble(),
    );
  }
}

class ProfitabilityData {
  final double? grossMargin;
  final double? operatingMargin;
  final double? profitMargin;
  final double? roe;
  final double? roa;

  ProfitabilityData({
    this.grossMargin,
    this.operatingMargin,
    this.profitMargin,
    this.roe,
    this.roa,
  });

  factory ProfitabilityData.fromJson(Map<String, dynamic> json) {
    return ProfitabilityData(
      grossMargin: (json['gross_margin'] as num?)?.toDouble(),
      operatingMargin: (json['operating_margin'] as num?)?.toDouble(),
      profitMargin: (json['profit_margin'] as num?)?.toDouble(),
      roe: (json['roe'] as num?)?.toDouble(),
      roa: (json['roa'] as num?)?.toDouble(),
    );
  }
}

class GrowthData {
  final double? revenueGrowth;
  final double? earningsGrowth;

  GrowthData({this.revenueGrowth, this.earningsGrowth});

  factory GrowthData.fromJson(Map<String, dynamic> json) {
    return GrowthData(
      revenueGrowth: (json['revenue_growth'] as num?)?.toDouble(),
      earningsGrowth: (json['earnings_growth'] as num?)?.toDouble(),
    );
  }
}

class PerShareData {
  final double? epsTrailing;
  final double? epsForward;
  final double? bookValue;
  final double? dividendRate;
  final double? dividendYield;

  PerShareData({
    this.epsTrailing,
    this.epsForward,
    this.bookValue,
    this.dividendRate,
    this.dividendYield,
  });

  factory PerShareData.fromJson(Map<String, dynamic> json) {
    return PerShareData(
      epsTrailing: (json['eps_trailing'] as num?)?.toDouble(),
      epsForward: (json['eps_forward'] as num?)?.toDouble(),
      bookValue: (json['book_value'] as num?)?.toDouble(),
      dividendRate: (json['dividend_rate'] as num?)?.toDouble(),
      dividendYield: (json['dividend_yield'] as num?)?.toDouble(),
    );
  }
}

class CompanyInfo {
  final String? sector;
  final String? industry;
  final int? employees;
  final String? country;
  final String? website;
  final String? description;

  CompanyInfo({
    this.sector,
    this.industry,
    this.employees,
    this.country,
    this.website,
    this.description,
  });

  factory CompanyInfo.fromJson(Map<String, dynamic> json) {
    return CompanyInfo(
      sector: json['sector'],
      industry: json['industry'],
      employees: json['employees'] as int?,
      country: json['country'],
      website: json['website'],
      description: json['description'],
    );
  }
}
