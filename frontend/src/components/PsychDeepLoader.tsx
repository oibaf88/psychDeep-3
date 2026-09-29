interface Props {
  size?: "sm" | "md" | "lg";
  label?: string;
  className?: string;
}

/**
 * Brand-native wait indicator used while screens or model-backed actions are
 * actually pending. The MP4 is muted, inline, looped and same-origin so it
 * does not add a third-party dependency or unexpected audio.
 *
 * Reduced-motion users receive the static mark instead of the animation.
 */
export default function PsychDeepLoader({ size = "md", label, className }: Props) {
  const classes = [
    "psychdeep-loader",
    `psychdeep-loader--${size}`,
    className,
  ].filter(Boolean).join(" ");

  return (
    <div
      className={classes}
      role={label ? "status" : undefined}
      aria-live={label ? "polite" : undefined}
    >
      <video
        className="psychdeep-loader__video"
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        poster="/psychDeep%20logo.png"
        aria-hidden="true"
      >
        <source src="/moving%20psychDeep%20logo.mp4" type="video/mp4" />
      </video>
      <img
        className="psychdeep-loader__fallback"
        src="/psychDeep%20logo.png"
        alt=""
        aria-hidden="true"
        draggable={false}
      />
      {label && <span className="psychdeep-loader__label">{label}</span>}
    </div>
  );
}
