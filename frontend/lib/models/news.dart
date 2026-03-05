class NewsItem {
  final String title;
  final String url;
  final String? source;
  final String? publishedAt;
  final String? summary;

  NewsItem({
    required this.title,
    required this.url,
    this.source,
    this.publishedAt,
    this.summary,
  });

  factory NewsItem.fromJson(Map<String, dynamic> json) {
    return NewsItem(
      title: json['title'] ?? '',
      url: json['url'] ?? '',
      source: json['source'],
      publishedAt: json['published_at'],
      summary: json['summary'],
    );
  }
}
