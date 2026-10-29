// Liveness probe for the container health check; touches no auth, DB or API.
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" });
}
