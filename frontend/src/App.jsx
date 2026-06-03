import AppRouter from "./AppRouter";
import MobileUpdateGate from "./components/mobile/MobileUpdateGate";

export default function App() {
  return (
    <MobileUpdateGate>
      <AppRouter />
    </MobileUpdateGate>
  );
}
