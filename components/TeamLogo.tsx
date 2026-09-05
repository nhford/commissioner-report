type Props = {
  src: string | null;
  alt: string;
  size?: "sm" | "md";
};

export default function TeamLogo({ src, alt, size = "md" }: Props) {
  const box = size === "sm" ? "h-6 w-6" : "h-8 w-8 md:h-10 md:w-10";
  if (!src) {
    const initial = alt.trim().charAt(0).toUpperCase() || "?";
    return (
      <span
        aria-hidden
        className={`${box} grid shrink-0 place-items-center rounded bg-neutral-200 text-xs font-bold text-neutral-700`}
      >
        {initial}
      </span>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      className={`${box} shrink-0 object-contain`}
    />
  );
}
