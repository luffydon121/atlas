"use client";

import Link from "next/link";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="hero">
      <h1>Something went wrong.</h1>
      <p>This page hit an unexpected problem. Your data is safe.</p>
      <div className="row" style={{ marginTop: 20 }}><button className="btn on" onClick={reset}>Try again</button><Link className="btn" href="/">Back to Today</Link></div>
    </div>
  );
}
