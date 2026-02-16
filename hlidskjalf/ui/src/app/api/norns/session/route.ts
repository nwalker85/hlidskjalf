import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import crypto from "crypto";

const COOKIE_NAME = "norns_session";
const SESSION_TTL_SECONDS = 60 * 60 * 24 * 30; // 30 days

// Lazy initialization to avoid build-time errors when env vars aren't available
let _encryptionKey: Buffer | null = null;

function getEncryptionKey(): Buffer {
  if (_encryptionKey) return _encryptionKey;
  
  const secret = process.env.NORNS_SESSION_SECRET || process.env.NEXTAUTH_SECRET;
  if (!secret) {
    throw new Error(
      "Missing NORNS_SESSION_SECRET or NEXTAUTH_SECRET for session encryption",
    );
  }
  
  _encryptionKey = crypto.createHash("sha256").update(secret).digest();
  return _encryptionKey;
}

interface SessionPayload {
  apiUrl: string;
  assistantId: string;
  threadId?: string | null;
  issuedAt: number;
}

function serializePayload(payload: SessionPayload): string {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", getEncryptionKey(), iv);
  const plaintext = Buffer.from(JSON.stringify(payload), "utf8");
  const encrypted = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return Buffer.concat([iv, authTag, encrypted]).toString("base64url");
}

function deserializePayload(token: string): SessionPayload | null {
  try {
    const raw = Buffer.from(token, "base64url");
    const iv = raw.subarray(0, 12);
    const authTag = raw.subarray(12, 28);
    const ciphertext = raw.subarray(28);
    const decipher = crypto.createDecipheriv(
      "aes-256-gcm",
      getEncryptionKey(),
      iv,
    );
    decipher.setAuthTag(authTag);
    const decrypted = Buffer.concat([
      decipher.update(ciphertext),
      decipher.final(),
    ]);
    return JSON.parse(decrypted.toString("utf8"));
  } catch (error) {
    console.error("Failed to decode norns session token:", error);
    return null;
  }
}

function setSessionCookie(token: string) {
  cookies().set({
    name: COOKIE_NAME,
    value: token,
    httpOnly: true,
    sameSite: "lax",
    secure: true,
    maxAge: SESSION_TTL_SECONDS,
    path: "/",
  });
}

function clearSessionCookie() {
  cookies().set({
    name: COOKIE_NAME,
    value: "",
    maxAge: 0,
    path: "/",
  });
}

function normalizeUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

export async function GET(request: NextRequest) {
  const tokenFromQuery = request.nextUrl.searchParams.get("token");
  const cookieToken = cookies().get(COOKIE_NAME)?.value;
  const token = tokenFromQuery || cookieToken;

  if (!token) {
    return NextResponse.json(
      { error: "Session not configured" },
      { status: 404 },
    );
  }

  const payload = deserializePayload(token);
  if (!payload) {
    if (!tokenFromQuery) {
      clearSessionCookie();
    }
    return NextResponse.json({ error: "Invalid session token" }, { status: 400 });
  }

  if (tokenFromQuery) {
    setSessionCookie(token);
  }

  return NextResponse.json({
    token,
    config: {
      apiUrl: payload.apiUrl,
      assistantId: payload.assistantId,
      threadId: payload.threadId ?? null,
    },
  });
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const apiUrl = typeof body.apiUrl === "string" ? body.apiUrl : "";
    const assistantId =
      typeof body.assistantId === "string" ? body.assistantId : "";
    const threadId =
      typeof body.threadId === "string" || body.threadId === null
        ? body.threadId
        : undefined;

    if (!apiUrl || !assistantId) {
      return NextResponse.json(
        { error: "apiUrl and assistantId are required" },
        { status: 400 },
      );
    }

    const normalizedPayload: SessionPayload = {
      apiUrl: normalizeUrl(apiUrl),
      assistantId: assistantId.trim(),
      threadId: threadId === undefined ? null : threadId,
      issuedAt: Date.now(),
    };

    const token = serializePayload(normalizedPayload);
    setSessionCookie(token);

    return NextResponse.json({
      token,
      config: {
        apiUrl: normalizedPayload.apiUrl,
        assistantId: normalizedPayload.assistantId,
        threadId: normalizedPayload.threadId,
      },
    });
  } catch (error) {
    console.error("Failed to save norns session:", error);
    return NextResponse.json(
      { error: "Failed to save session" },
      { status: 500 },
    );
  }
}

export async function DELETE() {
  clearSessionCookie();
  return NextResponse.json({ status: "cleared" });
}

