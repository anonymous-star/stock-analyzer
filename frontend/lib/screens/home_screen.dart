import 'dart:async';
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
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _loadingRec = false;
    // 백그라운드에서 추천 데이터 로드 (chip 표시용, UI 블로킹 없음)
    _loadRecommendationsSilently();
  }

  Future<void> _loadRecommendationsSilently() async {
    try {
      final data = await _api.getRecommendations(limit: 20);
      if (mounted) setState(() => _recommendations = data);
    } catch (_) {}
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
                _debounce?.cancel();
                if (v.length >= 2) {
                  _debounce = Timer(const Duration(milliseconds: 500), () => _search(v));
                }
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
        // 추천 데이터에서 매칭되는 종목 찾기
        final rec = _recommendations.where((rec) => rec.ticker == ticker).toList();
        Widget? chip;
        if (rec.isNotEmpty) {
          final s = rec.first;
          Color c;
          String label;
          if (s.isBuy) { c = Colors.red; label = '매수'; }
          else if (s.isSell) { c = Colors.blue; label = '매도'; }
          else { c = Colors.orange; label = '보유'; }
          chip = Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(6)),
            child: Text('$label ${s.confidence}%', style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
          );
        }
        return ListTile(
          leading: CircleAvatar(
            backgroundColor: Theme.of(context).colorScheme.primaryContainer,
            child: Text(ticker.substring(0, ticker.length > 0 ? 1 : 0),
                style: TextStyle(color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.bold)),
          ),
          title: Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text(ticker),
          trailing: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (chip != null) ...[chip, const SizedBox(width: 6)],
              Text(r['exchange'] as String? ?? '', style: const TextStyle(color: Colors.grey, fontSize: 12)),
            ],
          ),
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
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.analytics_outlined, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            const Text('종목을 검색하거나', style: TextStyle(fontSize: 15, color: Colors.grey)),
            const SizedBox(height: 4),
            const Text('새로고침으로 추천 분석을 시작하세요', style: TextStyle(fontSize: 15, color: Colors.grey)),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              icon: const Icon(Icons.refresh),
              label: const Text('추천 분석 시작'),
              onPressed: _loadRecommendations,
            ),
          ],
        ),
      );
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
              '※ 기술적·재무·거래량·뉴스 복합 지표 기반 자동 분석\n   투자 판단은 본인 책임입니다.',
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
                  // 추천 뱃지 + 확신도
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: recColor,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text('$recLabel ${r.confidence}%',
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        _confidenceLabel(r.confidence),
                        style: TextStyle(fontSize: 10, color: recColor, fontWeight: FontWeight.w500),
                      ),
                    ],
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
                  // 점수 (숫자 표시)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: recColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      '${r.score > 0 ? "+" : ""}${r.score}/${r.maxScore}',
                      style: TextStyle(fontSize: 12, color: recColor, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
              // 점수 breakdown
              if (r.scoreBreakdown != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    _breakdownChip('기술', r.scoreBreakdown!.technical, 8),
                    const SizedBox(width: 4),
                    _breakdownChip('재무', r.scoreBreakdown!.financial, 6),
                    const SizedBox(width: 4),
                    _breakdownChip('거래량', r.scoreBreakdown!.volume, 4),
                    if (r.scoreBreakdown!.momentum != 0) ...[
                      const SizedBox(width: 4),
                      _breakdownChip('반등', r.scoreBreakdown!.momentum, 3),
                    ],
                    if (r.scoreBreakdown!.news != 0) ...[
                      const SizedBox(width: 4),
                      _breakdownChip('뉴스', r.scoreBreakdown!.news, 3),
                    ],
                  ],
                ),
              ],
              // RSI + PER + 거래량
              const SizedBox(height: 6),
              Row(
                children: [
                  if (r.rsi != null)
                    Text('RSI ${r.rsi!.toStringAsFixed(1)}',
                        style: TextStyle(
                          fontSize: 12,
                          color: r.rsi! > 70 ? Colors.red : r.rsi! < 30 ? Colors.blue : Colors.grey[600],
                          fontWeight: FontWeight.w500,
                        )),
                  if (r.rsi != null && r.maTrend != null) const SizedBox(width: 8),
                  if (r.maTrend != null)
                    Text(
                      _trendLabel(r.maTrend!),
                      style: TextStyle(
                        fontSize: 12,
                        color: r.maTrend == 'bullish' ? Colors.red : r.maTrend == 'bearish' ? Colors.blue : Colors.grey,
                      ),
                    ),
                  if (r.peRatio != null) ...[
                    const SizedBox(width: 8),
                    Text('PER ${r.peRatio!.toStringAsFixed(1)}',
                        style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                  ],
                  if (r.volumeRatio != null) ...[
                    const SizedBox(width: 8),
                    Text('Vol ${r.volumeRatio!.toStringAsFixed(1)}x',
                        style: TextStyle(
                          fontSize: 12,
                          color: r.volumeRatio! > 1.5 ? Colors.amber[700] : Colors.grey[600],
                        )),
                  ],
                ],
              ),
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

  String _confidenceLabel(int confidence) {
    if (confidence >= 80) return '매우 강력';
    if (confidence >= 70) return '강력';
    if (confidence >= 60) return '양호';
    if (confidence >= 50) return '보통';
    return '약함';
  }

  Widget _breakdownChip(String label, int score, int max) {
    Color c;
    if (score > 0) {
      c = Colors.red;
    } else if (score < 0) {
      c = Colors.blue;
    } else {
      c = Colors.grey;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: c.withOpacity(0.08),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: c.withOpacity(0.2)),
      ),
      child: Text(
        '$label ${score > 0 ? "+" : ""}$score',
        style: TextStyle(fontSize: 10, color: c, fontWeight: FontWeight.w600),
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
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }
}
