import MobileUpdateModal from "./MobileUpdateModal";
import { useMobileAppUpdate } from "../../hooks/useMobileAppUpdate";

export default function MobileUpdateGate({ children }) {
  const {
    ready,
    showPrompt,
    forceUpdate,
    latest,
    downloading,
    error,
    dismissLater,
    startUpdate,
  } = useMobileAppUpdate();

  const blockApp = ready && forceUpdate && showPrompt;

  return (
    <>
      {blockApp ? (
        <div className="flex min-h-screen items-center justify-center bg-[var(--brand-bg,#0a0a0a)] p-4">
          <p className="text-center text-sm text-white/80">Azmus ERP — update required</p>
        </div>
      ) : (
        children
      )}
      <MobileUpdateModal
        open={ready && showPrompt}
        forceUpdate={forceUpdate}
        latest={latest}
        downloading={downloading}
        error={error}
        onUpdate={startUpdate}
        onLater={dismissLater}
      />
    </>
  );
}
