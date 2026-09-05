function VenmoIcon({ size = 22 }: { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 512 512"
      aria-hidden
      focusable="false"
    >
      <path
        fill="currentColor"
        d="M444.17 32H70.28C49.85 32 32 46.7 32 66.89V441.6c0 20.31 17.85 38.4 38.28 38.4h373.78c20.54 0 35.94-18.2 35.94-38.39V66.89C480.12 46.7 464.6 32 444.17 32M278 387H174.32l-41.57-248.56l90.75-8.62l22 176.87c20.53-33.45 45.88-86 45.88-121.87c0-19.62-3.36-33-8.61-44l82.63-16.72c9.56 15.78 13.86 32 13.86 52.57c-.01 65.5-55.92 150.59-101.26 210.33"
      />
    </svg>
  );
}

function LinkedInIcon({ size = 22 }: { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 448 512"
      fill="currentColor"
      aria-hidden
      focusable="false"
    >
      <path d="M100.28 448H7.4V148.9h92.88zm-46.44-340A53.79 53.79 0 0153.51 0a53.74 53.74 0 0153.09 53.61c0 29.65-23.44 53.64-53.26 53.64zM447.9 448h-92.68V302.4c0-34.7-.7-79.2-48.29-79.2-48.33 0-55.72 37.7-55.72 76.6V448h-92.74V148.9h89.05v40.8h1.3c12.4-23.5 42.55-48.3 87.53-48.3 93.6 0 110.82 61.7 110.82 141.8V448z" />
    </svg>
  );
}

function GitHubIcon({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
      focusable="false"
    >
      <path d="M12 .5C5.65.5.5 5.65.5 12A11.5 11.5 0 008 23.13c.6.11.82-.26.82-.58v-2.04c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.1-.74.08-.73.08-.73 1.22.09 1.87 1.25 1.87 1.25 1.08 1.86 2.83 1.32 3.52 1.01.11-.78.42-1.32.76-1.63-2.66-.3-5.47-1.33-5.47-5.94 0-1.31.47-2.38 1.24-3.22-.12-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23a11.3 11.3 0 016 0C16.2 4.82 17.2 5.14 17.2 5.14c.66 1.65.24 2.87.12 3.17.77.84 1.23 1.91 1.23 3.22 0 4.62-2.82 5.63-5.5 5.93.43.37.82 1.1.82 2.22v3.29c0 .32.22.7.83.58A11.52 11.52 0 0023.5 12C23.5 5.65 18.35.5 12 .5z" />
    </svg>
  );
}

const linkClass =
  "p-2 text-white/70 transition-colors hover:text-white hover:underline hover:underline-offset-2 hover:decoration-emerald-400";

export default function Footer() {
  const iconSize = 22;

  return (
    <footer className="mt-10 w-full text-center text-sm text-white/70">
      <p>Created by Noah Ford, MSCS @ CMU &apos;26</p>
      <nav
        className="flex items-center justify-center"
        aria-label="Creator links"
      >
        <a
          href="https://github.com/nhford"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Noah Ford on GitHub"
          className={linkClass}
        >
          <GitHubIcon size={iconSize} />
        </a>
        <a
          href="https://www.linkedin.com/in/nhford/"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Noah Ford on LinkedIn"
          className={linkClass}
        >
          <LinkedInIcon size={iconSize} />
        </a>
        <a
          href="https://venmo.com/Noah-Ford-57"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Noah Ford on Venmo"
          className={linkClass}
        >
          <VenmoIcon size={iconSize} />
        </a>
      </nav>
    </footer>
  );
}
