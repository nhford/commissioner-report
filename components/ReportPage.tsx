import type { ReactNode } from "react";

type Props = {
  title: string;
  updated?: string | null;
  how?: ReactNode;
  children: ReactNode;
};

export default function ReportPage({ title, updated, how, children }: Props) {
  return (
    <div>
      <h1 className="text-2xl font-bold md:text-3xl">{title}</h1>
      {updated ? <p className="mt-2 text-sm text-white/65">{updated}</p> : null}
      {how ? (
        <>
          <details className="mt-3 max-w-2xl md:hidden">
            <summary className="min-h-11 cursor-pointer text-sm text-white/70 underline decoration-white/40 underline-offset-2">
              How {title} works
            </summary>
            <p className="mt-2 text-sm text-white/70">{how}</p>
          </details>
          <p className="mt-3 hidden max-w-2xl text-sm text-white/70 md:block">{how}</p>
        </>
      ) : null}
      <div className="mt-6">{children}</div>
    </div>
  );
}
