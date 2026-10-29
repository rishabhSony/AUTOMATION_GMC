import type { UserJSON, WebhookEvent } from "@clerk/nextjs/server";
import { sql } from "drizzle-orm";
import { headers } from "next/headers";
import { Webhook } from "svix";

import { withSystemContext, type UserRole } from "@/db";
import { userRoleEnum, users } from "@/db/schema";

const ROLES = new Set<string>(userRoleEnum.enumValues);

function toUserRow(data: UserJSON) {
  const email =
    data.email_addresses.find((e) => e.id === data.primary_email_address_id)
      ?.email_address ?? data.email_addresses[0]?.email_address;
  if (!email) throw new Error(`Clerk user ${data.id} has no email address`);

  const fullName =
    [data.first_name, data.last_name].filter(Boolean).join(" ") || email;
  // Admins set the role on the invitation's public metadata; Clerk copies it to the user.
  const metadataRole = data.public_metadata?.role;
  const role =
    typeof metadataRole === "string" && ROLES.has(metadataRole)
      ? (metadataRole as UserRole)
      : undefined;

  return { clerkUserId: data.id, email, fullName, role };
}

export async function POST(req: Request) {
  const secret = process.env.CLERK_WEBHOOK_SIGNING_SECRET;
  if (!secret) {
    return new Response("CLERK_WEBHOOK_SIGNING_SECRET is not set", {
      status: 500,
    });
  }

  const h = await headers();
  const svixHeaders = {
    "svix-id": h.get("svix-id") ?? "",
    "svix-timestamp": h.get("svix-timestamp") ?? "",
    "svix-signature": h.get("svix-signature") ?? "",
  };
  const payload = await req.text();

  // svix 2.x verify() throws on a bad signature and returns nothing, so parse afterwards.
  try {
    new Webhook(secret).verify(payload, svixHeaders);
  } catch {
    return new Response("Invalid webhook signature", { status: 400 });
  }
  const event = JSON.parse(payload) as WebhookEvent;

  switch (event.type) {
    case "user.created":
    case "user.updated": {
      const row = toUserRow(event.data);
      await withSystemContext((tx) =>
        tx
          .insert(users)
          .values({ ...row, isActive: true })
          .onConflictDoUpdate({
            target: users.clerkUserId,
            set: {
              email: row.email,
              fullName: row.fullName,
              ...(row.role && { role: row.role }),
              updatedAt: sql`now()`,
            },
          }),
      );
      break;
    }
    case "user.deleted": {
      // Deactivate rather than delete: audit_logs and cases keep referencing the row.
      const clerkUserId = event.data.id;
      if (clerkUserId) {
        await withSystemContext((tx) =>
          tx
            .update(users)
            .set({ isActive: false, updatedAt: sql`now()` })
            .where(sql`${users.clerkUserId} = ${clerkUserId}`),
        );
      }
      break;
    }
  }

  return new Response(null, { status: 204 });
}
