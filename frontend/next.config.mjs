/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produce a minimal standalone server bundle for container images.
  output: "standalone",
};

export default nextConfig;
