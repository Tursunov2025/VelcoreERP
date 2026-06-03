import { registerPlugin } from "@capacitor/core";

export const AppUpdate = registerPlugin("AppUpdate", {
  web: () => import("./appUpdate.web.js"),
});

export async function downloadApk(url) {
  if (!url) throw new Error("APK URL missing");
  return AppUpdate.downloadApk({ url });
}
