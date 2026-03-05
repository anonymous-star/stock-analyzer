import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/stock.dart';
import '../models/analysis.dart';
import '../models/news.dart';
import '../models/recommendation.dart';

class ApiService {
  // Change this to your backend IP when running on a physical device
  static const String baseUrl = 'https://stock-analyzer-uvm7.onrender.com';

  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  final http.Client _client = http.Client();

  Future<T> _get<T>(String path, T Function(dynamic) parser) async {
    final uri = Uri.parse('$baseUrl$path');
    final response = await _client.get(uri).timeout(const Duration(seconds: 30));

    if (response.statusCode == 200) {
      final decoded = utf8.decode(response.bodyBytes);
      return parser(json.decode(decoded));
    } else {
      final body = json.decode(utf8.decode(response.bodyBytes));
      throw ApiException(
        statusCode: response.statusCode,
        message: body['detail']?.toString() ?? 'Request failed',
      );
    }
  }

  Future<Map<String, dynamic>> _post(String path, {Map<String, dynamic>? body}) async {
    final uri = Uri.parse('$baseUrl$path');
    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: body != null ? json.encode(body) : null,
    ).timeout(const Duration(seconds: 60));

    if (response.statusCode == 200) {
      final decoded = utf8.decode(response.bodyBytes);
      return json.decode(decoded) as Map<String, dynamic>;
    } else {
      final b = json.decode(utf8.decode(response.bodyBytes));
      throw ApiException(
        statusCode: response.statusCode,
        message: b['detail']?.toString() ?? 'Request failed',
      );
    }
  }

  // Search stocks
  Future<List<Map<String, dynamic>>> searchStocks(String query) async {
    final data = await _get<Map<String, dynamic>>(
      '/stocks/search?q=${Uri.encodeComponent(query)}',
      (json) => json as Map<String, dynamic>,
    );
    return List<Map<String, dynamic>>.from(data['results'] ?? []);
  }

  // Get current quote
  Future<StockQuote> getQuote(String ticker) async {
    return _get<StockQuote>(
      '/stocks/${Uri.encodeComponent(ticker)}/quote',
      (json) => StockQuote.fromJson(json as Map<String, dynamic>),
    );
  }

  // Get technical indicators
  Future<TechnicalData> getTechnical(String ticker) async {
    return _get<TechnicalData>(
      '/stocks/${Uri.encodeComponent(ticker)}/technical',
      (json) => TechnicalData.fromJson(json as Map<String, dynamic>),
    );
  }

  // Get financial data
  Future<FinancialData> getFinancials(String ticker) async {
    return _get<FinancialData>(
      '/stocks/${Uri.encodeComponent(ticker)}/financials',
      (json) => FinancialData.fromJson(json as Map<String, dynamic>),
    );
  }

  // Get news
  Future<List<NewsItem>> getNews(String ticker, {int limit = 10}) async {
    final data = await _get<Map<String, dynamic>>(
      '/stocks/${Uri.encodeComponent(ticker)}/news?limit=$limit',
      (json) => json as Map<String, dynamic>,
    );
    return (data['news'] as List? ?? [])
        .map((e) => NewsItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // Get price history
  Future<List<PricePoint>> getHistory(String ticker, {String period = '6mo', String interval = '1d'}) async {
    final data = await _get<Map<String, dynamic>>(
      '/stocks/${Uri.encodeComponent(ticker)}/history?period=$period&interval=$interval',
      (json) => json as Map<String, dynamic>,
    );
    return (data['data'] as List? ?? [])
        .map((e) => PricePoint.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // Get recommendations
  Future<List<RecommendedStock>> getRecommendations({int limit = 10}) async {
    final data = await _get<Map<String, dynamic>>(
      '/recommendations?limit=$limit',
      (json) => json as Map<String, dynamic>,
    );
    return (data['recommendations'] as List? ?? [])
        .map((e) => RecommendedStock.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // Run AI analysis
  Future<StockAnalysis> analyzeStock(String ticker) async {
    final data = await _post('/stocks/${Uri.encodeComponent(ticker)}/analyze');
    return StockAnalysis.fromJson(data);
  }
}

class ApiException implements Exception {
  final int statusCode;
  final String message;

  ApiException({required this.statusCode, required this.message});

  @override
  String toString() => 'ApiException($statusCode): $message';
}
