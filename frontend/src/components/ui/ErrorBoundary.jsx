import { Component } from "react";
import { translate } from "../../i18n/translations";

function LocalizedError({ message }) {
  const t = (key) => translate(document.documentElement.lang, key);
  return <div className="flex min-h-screen flex-col items-center justify-center bg-[#f5f6fa] p-6"><div className="max-w-md rounded-[32px] bg-white p-8 shadow-xl text-center"><h1 className="text-xl font-black text-red-600">{t("errors.generic")}</h1><p className="mt-4 text-sm text-gray-600">{message}</p><button type="button" onClick={() => window.location.reload()} className="mt-6 rounded-2xl bg-black px-6 py-3 text-white">{t("shell.reload")}</button></div></div>;
}

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return <LocalizedError message={this.state.error.message} />;
    }
    return this.props.children;
  }
}
