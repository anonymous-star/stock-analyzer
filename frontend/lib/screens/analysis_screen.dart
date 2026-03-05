import 'package:flutter/material.dart';
import '../models/analysis.dart';
import '../services/api_service.dart';

class AnalysisScreen extends StatefulWidget {
  final String ticker;
  final String? name;

  const AnalysisScreen({super.key, required this.ticker, this.name});

  @override
  State<AnalysisScreen> createState() => _AnalysisScreenState();
}

class _AnalysisScreenState extends State<AnalysisScreen> {
  final _api = ApiService();
  bool _isLoading = true;
  StockAnalysis? _analysis;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadAnalysis();
  }

  Future<void> _loadAnalysis() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final result = await _api.analyzeStock(widget.ticker);
      if (mounted) setState(() {
        _analysis = result;
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('AI 분석: ${widget.name ?? widget.ticker}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadAnalysis,
            tooltip: '다시 분석',
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Claude AI가 분석 중입니다...', style: TextStyle(fontSize: 15)),
            SizedBox(height: 8),
            Text('기술적 분석 · 재무제표 · 뉴스 통합 분석', style: TextStyle(fontSize: 12, color: Colors.grey)),
          ],
        ),
      );
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.orange),
              const SizedBox(height: 12),
              const Text('분석 오류', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey)),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                icon: const Icon(Icons.refresh),
                label: const Text('다시 시도'),
                onPressed: _loadAnalysis,
              ),
            ],
          ),
        ),
      );
    }

    final a = _analysis!;
    return ListView(
      padding: const EdgeInsets.only(bottom: 24),
      children: [
        _buildRecommendationCard(a),
        if (a.overallSummary != null) _buildSummaryCard('종합 의견', a.overallSummary!),
        if (a.investmentPoints.isNotEmpty) _buildListCard('핵심 투자 포인트', a.investmentPoints, Colors.green),
        if (a.riskFactors.isNotEmpty) _buildListCard('리스크 요인', a.riskFactors, Colors.orange),
        if (a.technicalSummary != null && a.technicalSummary!.isNotEmpty)
          _buildSummaryCard('기술적 분석', a.technicalSummary!),
        if (a.fundamentalSummary != null && a.fundamentalSummary!.isNotEmpty)
          _buildSummaryCard('펀더멘털 분석', a.fundamentalSummary!),
      ],
    );
  }

  Widget _buildRecommendationCard(StockAnalysis a) {
    Color recColor;
    String recText;
    IconData recIcon;

    if (a.isBuy) {
      recColor = Colors.red;
      recText = '매수';
      recIcon = Icons.trending_up;
    } else if (a.isSell) {
      recColor = Colors.blue;
      recText = '매도';
      recIcon = Icons.trending_down;
    } else {
      recColor = Colors.orange;
      recText = '보유';
      recIcon = Icons.trending_flat;
    }

    return Card(
      margin: const EdgeInsets.all(16),
      color: recColor.withOpacity(0.08),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: recColor.withOpacity(0.3), width: 1.5),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(recIcon, color: recColor, size: 32),
                const SizedBox(width: 8),
                Text(
                  recText,
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: recColor),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // Confidence
            Text('신뢰도', style: TextStyle(color: Colors.grey[600], fontSize: 13)),
            const SizedBox(height: 6),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(5, (i) {
                return Icon(
                  i < a.confidence ? Icons.star : Icons.star_outline,
                  color: recColor,
                  size: 24,
                );
              }),
            ),
            // Target price
            if (a.targetPriceLow != null || a.targetPriceHigh != null) ...[
              const SizedBox(height: 12),
              const Divider(),
              const SizedBox(height: 8),
              Text('목표 주가', style: TextStyle(color: Colors.grey[600], fontSize: 13)),
              const SizedBox(height: 4),
              Text(
                _formatTargetPrice(a.targetPriceLow, a.targetPriceHigh),
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSummaryCard(String title, String content) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 10),
            Text(content, style: const TextStyle(height: 1.5, fontSize: 14)),
          ],
        ),
      ),
    );
  }

  Widget _buildListCard(String title, List<String> items, Color color) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 10),
            ...items.asMap().entries.map((e) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 22,
                      height: 22,
                      decoration: BoxDecoration(
                        color: color.withOpacity(0.15),
                        shape: BoxShape.circle,
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        '${e.key + 1}',
                        style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(e.value, style: const TextStyle(fontSize: 14, height: 1.4)),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  String _formatTargetPrice(double? low, double? high) {
    if (low != null && high != null) {
      return '${_fmt(low)} ~ ${_fmt(high)}';
    }
    if (low != null) return _fmt(low);
    if (high != null) return _fmt(high);
    return '--';
  }

  String _fmt(double v) {
    if (v >= 1000) return v.toStringAsFixed(0).replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
    return v.toStringAsFixed(2);
  }
}
