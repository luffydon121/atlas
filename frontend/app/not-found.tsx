import Link from "next/link";

export default function NotFound() {
  return (
    <div className="hero">
      <h1>Page not found.</h1>
      <p>That page doesn&apos;t exist in ATLAS.</p>
      <div className="row" style={{ marginTop: 20 }}><Link className="btn on" href="/">Back to Today</Link></div>
    </div>
  );
}
