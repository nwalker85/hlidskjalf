import { Suspense } from "react";
import { MFAContent } from "./mfa-content";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export default function MFAPage() {
  return (
    <Suspense fallback={<MFASkeleton />}>
      <MFAContent />
    </Suspense>
  );
}

function MFASkeleton() {
  return (
    <Card>
      <CardHeader className="space-y-1">
        <Skeleton className="h-8 w-64 mx-auto" />
        <Skeleton className="h-4 w-48 mx-auto" />
      </CardHeader>
      <CardContent className="space-y-4">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-10 w-full" />
      </CardContent>
    </Card>
  );
}
