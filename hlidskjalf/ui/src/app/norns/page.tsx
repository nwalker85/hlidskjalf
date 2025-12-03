"use client";

import React from "react";
import dynamic from "next/dynamic";
import { Thread } from "@/components/thread";
import { StreamProvider } from "@/providers/Stream";
import { ThreadProvider } from "@/providers/Thread";
import { ArtifactProvider } from "@/components/thread/artifact";
import { Toaster } from "@/components/ui/sonner";
import { NornsConsole } from "@/components/console";

const NornsIntelligenceConsole = dynamic(
  () =>
    Promise.resolve(function NornsIntelligenceConsoleLayout() {
      return (
        <div className="fixed inset-0 overflow-hidden">
          <Toaster richColors position="top-center" />
          <ThreadProvider>
            <StreamProvider>
              <ArtifactProvider>
                <NornsConsole>
                  <div className="h-full w-full">
                    <Thread />
                  </div>
                </NornsConsole>
              </ArtifactProvider>
            </StreamProvider>
          </ThreadProvider>
        </div>
      );
    }),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-screen items-center justify-center bg-[#0A0F1C] text-raven-400">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="w-12 h-12 rounded-full border-2 border-raven-700 border-t-huginn-400 animate-spin" />
          </div>
          <span className="font-mono text-sm">Initializing Norns Intelligence Console...</span>
        </div>
      </div>
    ),
  },
);

export default function NornsAgentChatPage(): React.ReactNode {
  return (
    <React.Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-[#0A0F1C] text-raven-400">
          <div className="flex flex-col items-center gap-4">
            <div className="relative">
              <div className="w-12 h-12 rounded-full border-2 border-raven-700 border-t-huginn-400 animate-spin" />
            </div>
            <span className="font-mono text-sm">The Norns are weaving...</span>
          </div>
        </div>
      }
    >
      <NornsIntelligenceConsole />
    </React.Suspense>
  );
}
