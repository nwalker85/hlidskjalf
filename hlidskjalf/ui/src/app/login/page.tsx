"use client";

import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function LoginContent() {
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/";
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-norse">
      <div className="bg-raven-900/90 backdrop-blur-sm border border-raven-700 rounded-xl p-8 max-w-md w-full shadow-2xl">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 mx-auto mb-4 bg-gradient-to-br from-huginn-500 to-muninn-500 rounded-full flex items-center justify-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="w-10 h-10 text-white"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-raven-100">Hliðskjálf</h1>
          <p className="text-raven-400 mt-2">Odin&apos;s High Seat</p>
        </div>

        {/* Description */}
        <p className="text-raven-300 text-center mb-8">
          Sign in to observe all Nine Realms. The Norns await your counsel.
        </p>

        {/* SSO Button */}
        <button
          onClick={() => signIn("zitadel", { callbackUrl })}
          className="w-full py-3 px-4 bg-gradient-to-r from-huginn-600 to-huginn-500 hover:from-huginn-500 hover:to-huginn-400 text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-3 shadow-lg hover:shadow-huginn-500/25"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="w-5 h-5"
          >
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
            <polyline points="10 17 15 12 10 7" />
            <line x1="15" y1="12" x2="3" y2="12" />
          </svg>
          Sign in with Ravenhelm SSO
        </button>

        {/* Footer */}
        <p className="text-raven-500 text-xs text-center mt-8">
          Protected by Zitadel • Zero Trust Identity
        </p>
      </div>
    </div>
  );
}

function LoginLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-norse">
      <div className="animate-pulse text-raven-400">Loading...</div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginLoading />}>
      <LoginContent />
    </Suspense>
  );
}
