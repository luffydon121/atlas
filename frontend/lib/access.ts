// Optional passcode for phones and tablets on the same Wi-Fi. It is off unless ATLAS_PASSCODE is set.
export const COOKIE = "atlas_access";

export async function accessToken(passcode: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`atlas:${passcode}`));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
