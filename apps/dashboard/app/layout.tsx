import "./styles.css";
export const metadata = { title: "Watchtower", description: "Self-hosted website change monitoring" };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><header><strong>Watchtower</strong><nav>Overview · Monitors · Changes · Workers</nav></header><main>{children}</main></body></html>;
}
