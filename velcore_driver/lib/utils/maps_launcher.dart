import 'package:url_launcher/url_launcher.dart';

class MapsLauncher {
  /// Yandex Navigator — manzil matni yoki koordinatalar.
  static Future<bool> openNavigation({
    String? destinationAddress,
    double? latitude,
    double? longitude,
  }) async {
    if (latitude != null && longitude != null) {
      final naviUri = Uri.parse(
        'yandexnavi://build_route_on_map?lat_to=$latitude&lon_to=$longitude',
      );
      if (await canLaunchUrl(naviUri)) {
        return launchUrl(naviUri, mode: LaunchMode.externalApplication);
      }

      final mapsUri = Uri.parse(
        'https://yandex.com/maps/?rtext=~$latitude,$longitude&rtt=auto',
      );
      return launchUrl(mapsUri, mode: LaunchMode.externalApplication);
    }

    if (destinationAddress != null && destinationAddress.trim().isNotEmpty) {
      final encoded = Uri.encodeComponent(destinationAddress.trim());
      final naviUri = Uri.parse('yandexnavi://map_search?text=$encoded');
      if (await canLaunchUrl(naviUri)) {
        return launchUrl(naviUri, mode: LaunchMode.externalApplication);
      }

      final webUri = Uri.parse(
        'https://yandex.com/maps/?text=$encoded&rtt=auto',
      );
      return launchUrl(webUri, mode: LaunchMode.externalApplication);
    }

    return false;
  }
}
