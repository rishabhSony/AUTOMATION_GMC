import { redirect } from "next/navigation";

import { isSignedIn } from "@/lib/auth";

// Middleware already redirects `/`; this is the fallback if it is bypassed.
export default async function RootPage() {
  redirect((await isSignedIn()) ? "/dashboard" : "/login");
}
