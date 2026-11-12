import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, "../.."),
  transpilePackages: [
    "@caretwin/contracts",
    "@caretwin/domain",
    "@caretwin/safety",
    "@caretwin/shared",
  ],
  experimental: {
    externalDir: true,
  },
};

export default nextConfig;
