export function Skeleton({ className = "" }) {
  return (
    <div
      className={`animate-pulse rounded-2xl bg-gray-200 ${className}`}
      aria-hidden="true"
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="space-y-3 rounded-[28px] bg-white p-5 shadow-lg">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
}
