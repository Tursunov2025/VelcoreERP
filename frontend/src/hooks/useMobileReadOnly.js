import { useEffect, useState } from "react";
import { isNativeMobile } from "../mobile/capacitor.js";

export function useMobileReadOnly() {
  const [readOnly, setReadOnly] = useState(() => {
    if (typeof window === "undefined") return false;
    return isNativeMobile() || window.matchMedia("(max-width: 767px)").matches;
  });

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    const update = () => setReadOnly(isNativeMobile() || mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  return readOnly;
}
