export default async function Unlock({ searchParams }: { searchParams: Promise<{ failed?: string }> }) {
  const { failed } = await searchParams;
  return (
    <div className="unlock">
      <h1>ATLAS</h1>
      <p>Enter the passcode shown on your Mac.</p>
      <form method="post" action="/unlock/verify">
        <input className="input" type="password" name="passcode" autoFocus autoComplete="current-password" aria-label="Passcode" required />
        <button className="btn on">Unlock</button>
      </form>
      {failed && <p role="alert" style={{ color: "var(--down)" }}>That passcode is not right.</p>}
    </div>
  );
}
