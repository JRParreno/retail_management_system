import type { NextConfig } from "next";
import os from "os";

function lanHosts(): string[] {
  const hosts = new Set<string>(["127.0.0.1", "localhost"]);
  for (const addrs of Object.values(os.networkInterfaces())) {
    for (const addr of addrs ?? []) {
      if (addr.family !== "IPv4" || addr.internal) continue;
      hosts.add(addr.address);
    }
  }
  return [...hosts];
}

const nextConfig: NextConfig = {
  // Tablets/phones hit the LAN IP; Next blocks /_next/* cross-origin otherwise.
  // See https://nextjs.org/docs/app/api-reference/config/next-config-js/allowedDevOrigins
  allowedDevOrigins: lanHosts(),
};

export default nextConfig;
