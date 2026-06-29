import 'package:url_launcher/url_launcher.dart';

class MapsLauncher {
  /// Google Maps navigatsiyasi — manzil matni yoki koordinatalar.
  static Future<bool> openNavigation({
    String? destinationAddress,
    double? latitude,
    double? longitude,
  }) async {
    final Uri uri;
    if (latitude != null && longitude != null) {
      uri = Uri.parse(
        'google.navigation:q=$latitude,$longitude&mode=d',
      );
    } else if (destinationAddress != null && destinationAddress.trim().isNotEmpty) {
      final encoded = Uri.encodeComponent(destinationAddress.trim());
      uri = Uri.parse(
        'https://www.google.com/maps/dir/?api=1&destination=$encoded&travelmode=driving',
      );
    } else {
      return false;
    }

    if (await canLaunchUrl(uri)) {
      return launchUrl(uri, mode: LaunchMode.externalApplication);
    }

    // Fallback — browser orqali Google Maps
    if (destinationAddress != null && destinationAddress.trim().isNotEmpty) {
      final web = Uri.parse(
        'https://www.google.com/maps/search/?api=1&query=${Uri.encodeComponent(destinationAddress.trim())}',
      );
      return launchUrl(web, mode: LaunchMode.externalApplication);
    }
    return false;
  }
}
