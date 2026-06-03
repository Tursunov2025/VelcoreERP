export class AppUpdateWeb {
  async downloadApk({ url }) {
    window.open(url, "_blank", "noopener,noreferrer");
    return { downloadId: null };
  }
}
