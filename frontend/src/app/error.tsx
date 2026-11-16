"use client";

export default function ErrorPage({ reset }: Readonly<{ reset: () => void }>) {
  return (
    <main className="state-page">
      <div>
        <span className="eyebrow">Unexpected error</span>
        <h1>Something went wrong.</h1>
        <p>The page could not be loaded.</p>
        <button className="button button--primary" type="button" onClick={reset}>Try again</button>
      </div>
    </main>
  );
}

