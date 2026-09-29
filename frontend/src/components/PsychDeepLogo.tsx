interface Props {
  className?: string;
  alt?: string;
}

/** Static PsychDeep brand mark. The asset is repository-owned and same-origin. */
export default function PsychDeepLogo({ className, alt = "" }: Props) {
  return (
    <img
      className={className ? `psychdeep-logo ${className}` : "psychdeep-logo"}
      src="/psychDeep%20logo.png"
      alt={alt}
      draggable={false}
    />
  );
}
