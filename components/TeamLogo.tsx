type Props = {
  src: string | null;
  alt: string;
  size?: "sm" | "md" | "lg";
  circle?: boolean;
};

export default function TeamLogo({ src, alt, size = "md", circle = false }: Props) {
  const box =
    size === "sm"
      ? "h-6 w-6"
      : size === "lg"
        ? "h-24 w-24"
        : "h-8 w-8 md:h-10 md:w-10";
  const shape = circle ? "rounded-full object-cover" : "object-contain";
  if (!src) {
    const initial = alt.trim().charAt(0).toUpperCase() || "?";
    return (
      <span
        aria-hidden
        className={`${box} ${circle ? "rounded-full" : "rounded"} grid shrink-0 place-items-center bg-neutral-200 font-bold text-neutral-700 ${size === "lg" ? "text-2xl" : "text-xs"}`}
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
      className={`${box} shrink-0 ${shape}`}
    />
  );
}
