export default function LoadingSpinner({ label = "Yuklanmoqda..." }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-500">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-gray-200 border-t-black" />
      <p className="mt-4 text-sm">{label}</p>
    </div>
  );
}
