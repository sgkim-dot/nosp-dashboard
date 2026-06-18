import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Explicitly anchor Turbopack to this app directory so workspace
  // root inference doesn't crawl above apps/dashboard.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
