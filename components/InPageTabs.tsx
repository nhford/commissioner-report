type Tab<T extends string> = {
  id: T;
  label: string;
};

type Props<T extends string> = {
  tabs: Tab<T>[];
  value: T;
  onChange: (id: T) => void;
  label: string;
  scroll?: boolean;
};

export default function InPageTabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
  scroll = false,
}: Props<T>) {
  const buttons = tabs.map((tab) => {
    const active = tab.id === value;
    return (
      <button
        key={tab.id}
        type="button"
        role="tab"
        aria-selected={active}
        className={`${scroll ? "min-h-11 shrink-0" : "min-h-9"} px-3 text-sm whitespace-nowrap rounded border border-white/70 transition-colors touch-manipulation focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${
          active
            ? "bg-white text-black font-semibold"
            : "bg-transparent text-white hover:bg-white/10"
        }`}
        onClick={() => onChange(tab.id)}
      >
        {tab.label}
      </button>
    );
  });

  if (scroll) {
    return (
      <div
        className="overflow-x-auto overscroll-x-contain rounded-lg border border-white/25 p-2"
        role="tablist"
        aria-label={label}
      >
        <div className="flex w-max flex-nowrap gap-2">{buttons}</div>
      </div>
    );
  }

  return (
    <div
      className="flex flex-wrap items-center gap-2"
      role="tablist"
      aria-label={label}
    >
      {buttons}
    </div>
  );
}
