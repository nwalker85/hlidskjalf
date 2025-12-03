import { redirect } from "next/navigation";

export default function HomePage() {
  // Redirect to login by default
  redirect("/login");
}
