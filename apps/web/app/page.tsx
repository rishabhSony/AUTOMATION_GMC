import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

// Middleware already redirects `/`; this is the fallback if it is bypassed.
export default async function RootPage() {
  const { userId } = await auth();
  redirect(userId ? "/dashboard" : "/login");
}
