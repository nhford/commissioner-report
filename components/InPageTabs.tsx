type Tab<T extends string> = {
  id: T;
  label: string;
};

type Props<T extends string> = {
  tabs: Tab<T>[];
  value: T;
  onChange: (id: T) => void;
  label: string;
};

export default function InPageTabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
}: Props<T>) {
  return (
    <div
      className="flex flex-wrap items-center gap-2"
      role="tablist"
      aria-label={label}
    >
      {tabs.map((tab) => {
        const active = tab.id === value;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            className={`min-h-9 px-3 text-sm whitespace-nowrap rounded border border-white/70 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${
              active
                ? "bg-white text-black font-semibold"
                : "bg-transparent text-white hover:bg-white/10"
            }`}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
