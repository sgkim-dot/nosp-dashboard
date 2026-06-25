import { currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

// Maintenance/admin tooling gate. Add emails here when ops scope grows.
export const ADMIN_EMAILS = new Set(["sgkim@madup.com"]);

export async function getIsAdmin(): Promise<boolean> {
  const user = await currentUser();
  const email = user?.emailAddresses?.[0]?.emailAddress;
  return email !== undefined && ADMIN_EMAILS.has(email);
}

export async function requireAdmin(): Promise<void> {
  if (!(await getIsAdmin())) {
    redirect("/");
  }
}
