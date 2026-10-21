/**
 * Brand marks for GateKeep Health.
 * Draws with `currentColor` so the same component works on dark and light backgrounds.
 */

const MARK_VIEWBOX = "0 0 38.983 52";
const MARK_RATIO = 38.983 / 52;
const MARK_PATH =
  "M12.4881 22.5714H28.7517C33.8634 22.5714 37.7382 27.1832 36.8571 32.2184L34.9371 43.1899C34.248 47.1273 30.8289 50 26.8317 50H12.0314C7.66921 50 4.06505 46.5959 3.81619 42.2409L2.01374 10.698C1.74395 5.97668 5.49987 2 10.2289 2H16.6024C21.1469 2 24.831 5.68406 24.831 10.2286V15.7143";

export function GarryMark({
  size = 24,
  withEye = false,
  className,
}: {
  size?: number;
  withEye?: boolean;
  className?: string;
}) {
  return (
    <svg
      width={size * MARK_RATIO}
      height={size}
      viewBox={MARK_VIEWBOX}
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d={MARK_PATH}
        stroke="currentColor"
        strokeWidth={4}
        vectorEffect="non-scaling-stroke"
      />
      {withEye ? (
        <rect x="13.04" y="4.48" width="8" height="8" rx="2.67" fill="currentColor" />
      ) : null}
    </svg>
  );
}

export function Logo({
  size = 22,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center ${className ?? ""}`}
      style={{ gap: size * (4.97 / 48) }}
    >
      <GarryMark size={size} />

      <span
        className="font-display leading-none"
        style={{ fontSize: size * (49 / 48) }}
      >
        atekeep{" "}
        <span style={{ opacity: 0.55 }}>Health</span>
      </span>

      <span className="sr-only">GateKeep Health</span>
    </span>
  );
}
