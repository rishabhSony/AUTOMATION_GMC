import { sql } from "drizzle-orm";

import { closeDb, withSystemContext } from "./index";
import { sublimitRegistry, users } from "./schema";

// Placeholder accounts, one per role. clerk_user_id is replaced by the real
// Clerk ID when the Clerk webhook syncs the invited user (Phase 3).
const seedUsers: (typeof users.$inferInsert)[] = [
  {
    clerkUserId: "seed_admin",
    email: "admin@quotepulse.local",
    fullName: "Seed Admin",
    role: "admin",
  },
  {
    clerkUserId: "seed_underwriter",
    email: "underwriter@quotepulse.local",
    fullName: "Seed Underwriter",
    role: "underwriter",
  },
  {
    clerkUserId: "seed_sales_rm",
    email: "sales.rm@quotepulse.local",
    fullName: "Seed Sales RM",
    role: "sales_rm",
  },
  {
    clerkUserId: "seed_ops_analyst",
    email: "ops.analyst@quotepulse.local",
    fullName: "Seed Ops Analyst",
    role: "ops_analyst",
  },
];

// BRD §8.1 Procedure-Wise Sub-Limit Matching Registry (₹), in BRD order.
const registry: [
  procedure: string,
  option1: number,
  option2: number,
  option3: number,
  option4: number,
][] = [
  ["Coronary Artery Bypass Grafting (CABG)", 150000, 120000, 80000, 65000],
  ["Valve Replacement", 150000, 120000, 80000, 65000],
  ["PTCA (per event hospitalisation)", 130000, 100000, 70000, 50000],
  ["Total Knee Replacement (per event)", 130000, 100000, 70000, 50000],
  ["Total Hip Replacement", 150000, 120000, 80000, 65000],
  ["Arthroscopic Surgeries", 150000, 120000, 80000, 65000],
  ["Cholecystectomy", 35000, 25000, 20000, 20000],
  ["Kidney Stone Removal (incl. DJ Stent)", 35000, 30000, 25000, 20000],
  ["Appendectomy", 30000, 25000, 20000, 15000],
  ["Hysterectomy", 35000, 25000, 20000, 15000],
  ["Fistulectomy", 35000, 25000, 20000, 15000],
  ["Septoplasty", 35000, 25000, 20000, 15000],
  ["Hernia Repair", 35000, 25000, 20000, 15000],
  ["Haemorrhoidectomy", 25000, 20000, 15000, 15000],
  ["Tympanoplasty", 25000, 20000, 15000, 15000],
  ["Arthroscopy", 25000, 20000, 10000, 10000],
  ["Cataract (one eye)", 35000, 25000, 20000, 15000],
  ["Tonsillectomy", 20000, 15000, 10000, 10000],
  ["Dialysis (per session)", 5000, 4000, 2000, 2000],
];

async function main() {
  // users is under forced RLS; the seed is a trusted system writer.
  await withSystemContext(async (db) => {
    await db.insert(users).values(seedUsers).onConflictDoNothing();

    await db
      .insert(sublimitRegistry)
      .values(
        registry.map(([procedureName, o1, o2, o3, o4], i) => ({
          procedureName,
          option1Amount: o1.toFixed(2),
          option2Amount: o2.toFixed(2),
          option3Amount: o3.toFixed(2),
          option4Amount: o4.toFixed(2),
          displayOrder: i + 1,
        })),
      )
      .onConflictDoUpdate({
        target: sublimitRegistry.procedureName,
        set: {
          option1Amount: sql`excluded.option_1_amount`,
          option2Amount: sql`excluded.option_2_amount`,
          option3Amount: sql`excluded.option_3_amount`,
          option4Amount: sql`excluded.option_4_amount`,
          displayOrder: sql`excluded.display_order`,
          updatedAt: sql`now()`,
        },
      });

    const [{ userCount }] = await db
      .select({ userCount: sql<number>`count(*)::int` })
      .from(users);
    const [{ registryCount }] = await db
      .select({ registryCount: sql<number>`count(*)::int` })
      .from(sublimitRegistry);
    console.log(
      `Seeded: users=${userCount}, sublimit_registry=${registryCount}`,
    );
  });
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(closeDb);
