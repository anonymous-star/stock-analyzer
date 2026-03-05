import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';
import '../models/recommendation.dart';
import 'stock_detail_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _api = ApiService();
  final _searchController = TextEditingController();

  // 추천 종목
  List<RecommendedStock> _recommendations = [];
  bool _loadingRec = true;
  String? _recError;

  // 검색
  bool _isSearching = false;
  List<Map<String, dynamic>> _searchResults = [];
  String? _searchError;

  @override
  void initState() {
    super.initState();
    _loadRecommendations();
  }

  Future<void> _loadRecommendations() async {
    setState(() {
      _loadingRec = true;
      _recError = null;
    });
    try {
      final data = await _api.getRecommendations(limit: 20);
      if (mounted) setState(() {
        _recommendations = data;
        _loadingRec = false;
      });
    } catch (e) {
      if (mounted) setState(() {
        _recError = e.toString();
        _loadingRec = false;
      });
    }
  }

  Future<void> _search(String query) async {
    if (query.trim().isEmpty) {
      setState(() { _searchResults = []; _searchError = null; });
      return;
    }
    setState(() { _isSearching = true; _searchError = null; });
    try {
      final results = await _api.searchStocks(query.trim());
      if (mounted) setState(() {
        _searchResults = results;
        _isSearching = false;
        if (results.isEmpty) _searchError = '검색 결과가 없습니다';
      });
    } catch (e) {
      if (mounted) setState(() {
        _isSearching = false;
        _searchError = '검색 오류: $e';
      });
    }
  }

  void _goToDetail(String ticker, String? name) {
    Navigator.push(context, MaterialPageRoute(
      builder: (_) => StockDetailScreen(ticker: ticker, name: name),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final isShowingSearch = _searchController.text.isNotEmpty;
    return Scaffold(
      appBar: AppBar(
        title: const Text('주식 추천', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 20)),
        actions: [
          if (!isShowingSearch)
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _loadRecommendations,
              tooltip: '새로고침',
            ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(60),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: SearchBar(
              controller: _searchController,
              hintText: '종목 검색 (AAPL, 005930, 삼성전자...)',
              leading: const Icon(Icons.search, size: 20),
              trailing: [
                if (_searchController.text.isNotEmpty)
                  IconButton(
                    icon: const Icon(Icons.clear, size: 18),
                    onPressed: () {
                      _searchController.clear();
                      setState(() { _searchResults = []; _searchError = null; });
                    },
                  ),
              ],
              onChanged: (v) {
                setState(() {});
                if (v.length >= 2) _search(v);
              },
              onSubmitted: _search,
            ),
          ),
        ),
      ),
      body: isShowingSearch ? _buildSearchResults() : _buildRecommendations(),
    );
  }

  // ── 검색 결과 ──────────────────────────────────────────
  Widget _buildSearchResults() {
    if (_isSearching) return const Center(child: CircularProgressIndicator());
    if (_searchError != null) return Center(child: Text(_searchError!, style: const TextStyle(color: Colors.grey)));
    if (_searchResults.isEmpty) return const Center(child: Text('검색어를 입력하세요'));

    return ListView.builder(
      padding: const EdgeInsets.only(top: 8),
      itemCount: _searchResults.length,
      itemBuilder: (_, i) {
        final r = _searchResults[i];
        final ticker = r['ticker'] as String? ?? '';
        final name = r['name'] as String? ?? ticker;
        return ListTile(
          leading: CircleAvatar(
            backgroundColor: Theme.of(context).colorScheme.primaryContainer,
            child: Text(ticker.substring(0, 1),
                style: TextStyle(color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.bold)),
          ),
          title: Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text(ticker),
          trailing: Text(r['exchange'] as String? ?? '', style: const TextStyle(color: Colors.grey, fontSize: 12)),
          onTap: () => _goToDetail(ticker, name),
        );
      },
    );
  }

  // ── 추천 종목 ───────────────────────────────────────────
  Widget _buildRecommendations() {
    if (_loadingRec) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('종목 분석 중...', style: TextStyle(fontSize: 15)),
            SizedBox(height: 6),
            Text('한국/미국 주요 종목 기술적 분석', style: TextStyle(fontSize: 12, color: Colors.grey)),
          ],
        ),
      );
    }

    if (_recError != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.wifi_off, size: 48, color: Colors.grey),
            const SizedBox(height: 12),
            const Text('서버 연결 실패', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text('백엔드 서버가 실행 중인지 확인하세요', style: TextStyle(color: Colors.grey[600], fontSize: 13)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              icon: const Icon(Icons.refresh),
              label: const Text('다시 시도'),
              onPressed: _loadRecommendations,
            ),
          ],
        ),
      );
    }

    if (_recommendations.isEmpty) {
      return const Center(child: Text('추천 종목이 없습니다'));
    }

    final buyList = _recommendations.where((r) => r.isBuy).toList();
    final holdList = _recommendations.where((r) => !r.isBuy && !r.isSell).toList();
    final sellList = _recommendations.where((r) => r.isSell).toList();

    return RefreshIndicator(
      onRefresh: _loadRecommendations,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 32),
        children: [
          if (buyList.isNotEmpty) ...[
            _sectionHeader('🔴 매수 추천', buyList.length, Colors.red),
            ...buyList.map((r) => _buildRecCard(r)),
          ],
          if (holdList.isNotEmpty) ...[
            _sectionHeader('🟡 보유 / 관망', holdList.length, Colors.orange),
            ...holdList.map((r) => _buildRecCard(r)),
          ],
          if (sellList.isNotEmpty) ...[
            _sectionHeader('🔵 매도 / 주의', sellList.length, Colors.blue),
            ...sellList.map((r) => _buildRecCard(r)),
          ],
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: Text(
              '※ 기술적 지표(MA·RSI·MACD·볼린저밴드) 기반 자동 분석\n   투자 판단은 본인 책임입니다.',
              style: TextStyle(fontSize: 11, color: Colors.grey),
            ),
          ),
        ],
      ),
    );
  }

  Widget _sectionHeader(String title, int count, Color color) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 6),
      child: Row(
        children: [
          Text(title, style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: color)),
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
            decoration: BoxDecoration(
              color: color.withOpacity(0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text('$count', style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _buildRecCard(RecommendedStock r) {
    final isUp = (r.changePercent ?? 0) >= 0;
    final priceColor = isUp ? Colors.red : Colors.blue;

    Color recColor;
    String recLabel;
    if (r.isBuy) {
      recColor = Colors.red;
      recLabel = '매수';
    } else if (r.isSell) {
      recColor = Colors.blue;
      recLabel = '매도';
    } else {
      recColor = Colors.orange;
      recLabel = '보유';
    }

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
      child: InkWell(
        onTap: () => _goToDetail(r.ticker, r.name),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 상단: 종목명 + 추천 뱃지
              Row(
                children: [
                  CircleAvatar(
                    radius: 18,
                    backgroundColor: recColor.withOpacity(0.12),
                    child: Text(
                      r.ticker.split('.').first.substring(0, 1),
                      style: TextStyle(color: recColor, fontWeight: FontWeight.bold, fontSize: 14),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(r.name,
                            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                            overflow: TextOverflow.ellipsis),
                        Text(r.ticker, style: TextStyle(color: Colors.grey[500], fontSize: 11)),
                      ],
                    ),
                  ),
                  // 추천 뱃지
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: recColor,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(recLabel,
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              // 중단: 가격 + 등락률
              Row(
                children: [
                  Text(
                    _formatPrice(r.currentPrice, r.currency),
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(width: 8),
                  Icon(isUp ? Icons.arrow_upward : Icons.arrow_downward, size: 14, color: priceColor),
                  Text(
                    '${isUp ? '+' : ''}${r.changePercent?.toStringAsFixed(2) ?? '0.00'}%',
                    style: TextStyle(color: priceColor, fontWeight: FontWeight.w600, fontSize: 13),
                  ),
                  const Spacer(),
                  // 점수
                  Row(
                    children: [
                      const Text('점수 ', style: TextStyle(fontSize: 11, color: Colors.grey)),
                      ...List.generate(5, (i) {
                        final filled = i < r.score.abs().clamp(0, 5);
                        return Icon(
                          filled ? Icons.circle : Icons.circle_outlined,
                          size: 8,
                          color: filled ? recColor : Colors.grey[300],
                        );
                      }),
                    ],
                  ),
                ],
              ),
              // RSI
              if (r.rsi != null) ...[
                const SizedBox(height: 6),
                Row(
                  children: [
                    Text('RSI ${r.rsi!.toStringAsFixed(1)}',
                        style: TextStyle(
                          fontSize: 12,
                          color: r.rsi! > 70 ? Colors.red : r.rsi! < 30 ? Colors.blue : Colors.grey[600],
                          fontWeight: FontWeight.w500,
                        )),
                    const SizedBox(width: 8),
                    if (r.maTrend != null)
                      Text(
                        _trendLabel(r.maTrend!),
                        style: TextStyle(
                          fontSize: 12,
                          color: r.maTrend == 'bullish' ? Colors.red : r.maTrend == 'bearish' ? Colors.blue : Colors.grey,
                        ),
                      ),
                  ],
                ),
              ],
              // 이유
              if (r.reasons.isNotEmpty) ...[
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: r.reasons.map((reason) {
                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: recColor.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: recColor.withOpacity(0.2)),
                      ),
                      child: Text(reason, style: TextStyle(fontSize: 11, color: recColor.withOpacity(0.9))),
                    );
                  }).toList(),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  String _trendLabel(String trend) {
    switch (trend) {
      case 'bullish': return '▲ 상승추세';
      case 'bearish': return '▼ 하락추세';
      default: return '— 중립';
    }
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
    _searchController.dispose();
    super.dispose();
  }
}
