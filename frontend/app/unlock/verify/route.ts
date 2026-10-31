import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { accessToken, COOKIE } from "@/lib/access";

export async function POST(request: Request) {
  const expected = process.env.ATLAS_PASSCODE ?? "";
  const form = await request.formData();
  const given = String(form.get("passcode") ?? "");
  const [a, b] = await Promise.all([accessToken(given), accessToken(expected)]);
  const origin = new URL(request.url);
  const host = request.headers.get("host") ?? origin.host;
  const back = (path: string) => NextResponse.redirect(`http://${host}${path}`, 303);
  if (!expected || !timingSafeEqual(Buffer.from(a), Buffer.from(b))) {
    await new Promise((resolve) => setTimeout(resolve, 800));
    return back("/unlock?failed=1");
  }
  const response = back("/");
  response.cookies.set(COOKIE, a, { httpOnly: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 30 });
  return response;
}
