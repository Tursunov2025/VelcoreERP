import { Component } from "react";

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
      return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-[#f5f6fa] p-6">
          <div className="max-w-md rounded-[32px] bg-white p-8 shadow-xl text-center">
            <h1 className="text-xl font-black text-red-600">Xatolik yuz berdi</h1>
            <p className="mt-4 text-sm text-gray-600">{this.state.error.message}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-6 rounded-2xl bg-black px-6 py-3 text-white"
            >
              Qayta yuklash
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
