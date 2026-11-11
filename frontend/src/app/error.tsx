"use client";

export default function ErrorPage({ reset }: Readonly<{ reset: () => void }>) {
  return (
    <main>
      <h1>Something went wrong.</h1>
      <p className="lede">The page could not be loaded.</p>
      <button type="button" onClick={reset}>Try again</button>
    </main>
  );
}

