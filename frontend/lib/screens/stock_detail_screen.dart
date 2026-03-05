import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';
import '../models/stock.dart';
import '../models/analysis.dart';
import '../models/news.dart';
import '../widgets/technical_chart.dart';
import '../widgets/indicator_widget.dart';
import '../widgets/news_card.dart';
import 'analysis_screen.dart';

class StockDetailScreen extends StatefulWidget {
  final String ticker;
  final String? name;

  const StockDetailScreen({super.key, required this.ticker, this.name});

  @override
  State<StockDetailScreen> createState() => _StockDetailScreenState();
}

class _StockDetailScreenState extends State<StockDetailScreen>
    with SingleTickerProviderStateMixin {
  final _api = ApiService();
  late TabController _tabController;

  // Data
  StockQuote? _quote;
  List<PricePoint> _history = [];
  TechnicalData? _technical;
  FinancialData? _financials;
  List<NewsItem> _news = [];

  // Loading states
  bool _loadingQuote = true;
  bool _loadingHistory = true;
  bool _loadingTechnical = true;
  bool _loadingFinancials = true;
  bool _loadingNews = true;

  String _selectedPeriod = '6mo';
  final _periods = ['1mo', '3mo', '6mo', '1y', '2y'];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _loadAll();
  }

  void _loadAll() {
    _loadQuote();
    _loadHistory();
    _loadTechnical();
    _loadFinancials();
    _loadNews();
  }

  Future<void> _loadQuote() async {
    try {
      final data = await _api.getQuote(widget.ticker);
      if (mounted) setState(() { _quote = data; _loadingQuote = false; });
    } catch (_) {
      if (mounted) setState(() => _loadingQuote = false);
    }
  }

  Future<void> _loadHistory() async {
    setState(() => _loadingHistory = true);
    try {
      final data = await _api.getHistory(widget.ticker, period: _selectedPeriod);
      if (mounted) setState(() { _history = data; _loadingHistory = false; });
    } catch (_) {
      if (mounted) setState(() => _loadingHistory = false);
    }
  }

  Future<void> _loadTechnical() async {
    try {
      final data = await _api.getTechnical(widget.ticker);
      if (mounted) setState(() { _technical = data; _loadingTechnical = false; });
    } catch (_) {
      if (mounted) setState(() => _loadingTechnical = false);
    }
  }

  Future<void> _loadFinancials() async {
    try {
      final data = await _api.getFinancials(widget.ticker);
      if (mounted) setState(() { _financials = data; _loadingFinancials = false; });
    } catch (_) {
      if (mounted) setState(() => _loadingFinancials = false);
    }
  }

  Future<void> _loadNews() async {
    try {
      final data = await _api.getNews(widget.ticker);
      if (mounted) setState(() { _news = data; _loadingNews = false; });
    } catch (_) {
      if (mounted) setState(() => _loadingNews = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final name = _quote?.name ?? widget.name ?? widget.ticker;
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            Text(widget.ticker, style: const TextStyle(fontSize: 12, color: Colors.grey)),
          ],
        ),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: '차트'),
            Tab(text: '기술적'),
            Tab(text: '재무'),
            Tab(text: '뉴스'),
          ],
        ),
      ),
      body: Column(
        children: [
          // Price header
          _buildPriceHeader(),
          // Tabs
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                _buildChartTab(),
                _buildTechnicalTab(),
                _buildFinancialsTab(),
                _buildNewsTab(),
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => AnalysisScreen(ticker: widget.ticker, name: name),
            ),
          );
        },
        icon: const Icon(Icons.psychology),
        label: const Text('AI 분석'),
      ),
    );
  }

  Widget _buildPriceHeader() {
    if (_loadingQuote) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Center(child: LinearProgressIndicator()),
      );
    }
    if (_quote == null) return const SizedBox.shrink();

    final isUp = _quote!.isUp;
    final color = isUp ? Colors.red : Colors.blue;
    final priceStr = _formatPrice(_quote!.currentPrice, _quote!.currency);
    final changeStr = _quote!.changePercent != null
        ? '${isUp ? '+' : ''}${_quote!.changePercent!.toStringAsFixed(2)}%'
        : '--';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(bottom: BorderSide(color: Colors.grey.withOpacity(0.2))),
      ),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(priceStr, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
              Row(
                children: [
                  Icon(isUp ? Icons.arrow_upward : Icons.arrow_downward, color: color, size: 14),
                  Text(
                    changeStr,
                    style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 14),
                  ),
                ],
              ),
            ],
          ),
          const Spacer(),
          if (_quote!.weekHigh52 != null || _quote!.weekLow52 != null)
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text('52주 최고: ${_formatPrice(_quote!.weekHigh52, _quote!.currency)}',
                    style: const TextStyle(fontSize: 11, color: Colors.grey)),
                Text('52주 최저: ${_formatPrice(_quote!.weekLow52, _quote!.currency)}',
                    style: const TextStyle(fontSize: 11, color: Colors.grey)),
              ],
            ),
        ],
      ),
    );
  }

  Widget _buildChartTab() {
    return ListView(
      children: [
        // Period selector
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Row(
            children: _periods.map((p) {
              final selected = p == _selectedPeriod;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: GestureDetector(
                  onTap: () {
                    setState(() => _selectedPeriod = p);
                    _loadHistory();
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                    decoration: BoxDecoration(
                      color: selected ? Theme.of(context).colorScheme.primary : Colors.transparent,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: selected ? Theme.of(context).colorScheme.primary : Colors.grey.withOpacity(0.3),
                      ),
                    ),
                    child: Text(
                      p,
                      style: TextStyle(
                        color: selected ? Colors.white : Colors.grey[700],
                        fontSize: 13,
                        fontWeight: selected ? FontWeight.bold : FontWeight.normal,
                      ),
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ),
        // Chart
        _loadingHistory
            ? const SizedBox(height: 250, child: Center(child: CircularProgressIndicator()))
            : _history.isEmpty
                ? const SizedBox(height: 250, child: Center(child: Text('차트 데이터 없음')))
                : SizedBox(
                    height: 250,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(8, 8, 16, 8),
                      child: TechnicalChart(data: _history, period: _selectedPeriod),
                    ),
                  ),
      ],
    );
  }

  Widget _buildTechnicalTab() {
    if (_loadingTechnical) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_technical == null) {
      return const Center(child: Text('기술적 데이터를 불러올 수 없습니다'));
    }
    return SingleChildScrollView(child: IndicatorWidget(data: _technical!));
  }

  Widget _buildFinancialsTab() {
    if (_loadingFinancials) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_financials == null) {
      return const Center(child: Text('재무 데이터를 불러올 수 없습니다'));
    }
    return ListView(
      padding: const EdgeInsets.only(bottom: 24),
      children: [
        if (_financials!.companyInfo?.sector != null) _buildCompanyInfo(),
        if (_financials!.valuation != null) _buildValuationCard(),
        if (_financials!.profitability != null) _buildProfitabilityCard(),
        if (_financials!.growth != null) _buildGrowthCard(),
        if (_financials!.perShare != null) _buildPerShareCard(),
      ],
    );
  }

  Widget _buildCompanyInfo() {
    final info = _financials!.companyInfo!;
    return Card(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (info.sector != null) _chip(info.sector!, Colors.blue),
                if (info.industry != null) ...[
                  const SizedBox(width: 6),
                  _chip(info.industry!, Colors.purple),
                ],
              ],
            ),
            if (info.description != null && info.description!.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(info.description!, style: const TextStyle(fontSize: 12, height: 1.4, color: Colors.grey)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 12)),
    );
  }

  Widget _buildValuationCard() {
    final v = _financials!.valuation!;
    return _buildFinCard('밸류에이션', [
      _finRow('PER (후행)', v.peRatio, suffix: '배'),
      _finRow('PER (선행)', v.forwardPe, suffix: '배'),
      _finRow('PBR', v.pbRatio, suffix: '배'),
      _finRow('PSR', v.psRatio, suffix: '배'),
      _finRow('PEG', v.pegRatio),
      _finRow('EV/EBITDA', v.evEbitda, suffix: '배'),
    ]);
  }

  Widget _buildProfitabilityCard() {
    final p = _financials!.profitability!;
    return _buildFinCard('수익성', [
      _finRow('매출 총이익률', p.grossMargin, isPercent: true),
      _finRow('영업이익률', p.operatingMargin, isPercent: true),
      _finRow('순이익률', p.profitMargin, isPercent: true),
      _finRow('ROE', p.roe, isPercent: true),
      _finRow('ROA', p.roa, isPercent: true),
    ]);
  }

  Widget _buildGrowthCard() {
    final g = _financials!.growth!;
    return _buildFinCard('성장성', [
      _finRow('매출 성장률', g.revenueGrowth, isPercent: true),
      _finRow('이익 성장률', g.earningsGrowth, isPercent: true),
    ]);
  }

  Widget _buildPerShareCard() {
    final ps = _financials!.perShare!;
    return _buildFinCard('주당 지표', [
      _finRow('EPS (후행)', ps.epsTrailing),
      _finRow('EPS (선행)', ps.epsForward),
      _finRow('BPS', ps.bookValue),
      _finRow('배당금', ps.dividendRate),
      _finRow('배당 수익률', ps.dividendYield, isPercent: true),
    ]);
  }

  Widget _buildFinCard(String title, List<Widget> rows) {
    final nonNull = rows.where((w) => w is! SizedBox).toList();
    if (nonNull.isEmpty) return const SizedBox.shrink();
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const Divider(height: 16),
            ...rows,
          ],
        ),
      ),
    );
  }

  Widget _finRow(String label, double? value, {bool isPercent = false, String suffix = ''}) {
    if (value == null) return const SizedBox.shrink();
    String valueStr;
    if (isPercent) {
      final pct = value * 100;
      valueStr = '${pct.toStringAsFixed(1)}%';
    } else if (suffix.isNotEmpty) {
      valueStr = '${value.toStringAsFixed(2)}$suffix';
    } else {
      valueStr = value.toStringAsFixed(2);
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 13)),
          Text(valueStr, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _buildNewsTab() {
    if (_loadingNews) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_news.isEmpty) {
      return const Center(child: Text('뉴스를 불러올 수 없습니다'));
    }
    return ListView.builder(
      padding: const EdgeInsets.only(top: 8, bottom: 24),
      itemCount: _news.length,
      itemBuilder: (_, i) => NewsCard(news: _news[i]),
    );
  }

  String _formatPrice(double? price, String? currency) {
    if (price == null) return '--';
    if (currency == 'KRW') {
      return '${NumberFormat('#,##0').format(price.toInt())}원';
    }
    return '\$${price.toStringAsFixed(2)}';
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }
}
