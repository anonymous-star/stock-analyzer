import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/news.dart';

class NewsCard extends StatelessWidget {
  final NewsItem news;

  const NewsCard({super.key, required this.news});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      child: InkWell(
        onTap: () => _openUrl(news.url),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                news.title,
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14, height: 1.3),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
              if (news.summary != null && news.summary!.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  news.summary!,
                  style: TextStyle(fontSize: 12, color: Colors.grey[600], height: 1.4),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              const SizedBox(height: 8),
              Row(
                children: [
                  if (news.source != null && news.source!.isNotEmpty)
                    Text(
                      news.source!,
                      style: TextStyle(fontSize: 11, color: Colors.grey[500]),
                    ),
                  const Spacer(),
                  if (news.publishedAt != null)
                    Text(
                      _formatDate(news.publishedAt!),
                      style: TextStyle(fontSize: 11, color: Colors.grey[500]),
                    ),
                  const SizedBox(width: 4),
                  Icon(Icons.open_in_new, size: 12, color: Colors.grey[400]),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(String dateStr) {
    try {
      final dt = DateTime.parse(dateStr);
      final now = DateTime.now();
      final diff = now.difference(dt);
      if (diff.inHours < 24) return '${diff.inHours}시간 전';
      if (diff.inDays < 7) return '${diff.inDays}일 전';
      return '${dt.month}/${dt.day}';
    } catch (_) {
      return dateStr.substring(0, 10);
    }
  }

  Future<void> _openUrl(String url) async {
    if (url.isEmpty) return;
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}
