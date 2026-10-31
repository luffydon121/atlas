import { type NextRequest, NextResponse } from "next/server";
import { accessToken, COOKIE } from "@/lib/access";

export async function proxy(request: NextRequest) {
  const passcode = process.env.ATLAS_PASSCODE;
  if (!passcode) return NextResponse.next();
  if (request.cookies.get(COOKIE)?.value === (await accessToken(passcode))) return NextResponse.next();
  if (request.nextUrl.pathname.startsWith("/api/")) return NextResponse.json({ detail: "Locked" }, { status: 401 });
  return NextResponse.redirect(new URL("/unlock", `http://${request.headers.get("host")}`));
}

export const config = { matcher: ["/((?!_next/|unlock|icon.svg|manifest.webmanifest|maplibre-gl-).*)"] };
