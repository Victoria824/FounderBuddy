import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // 确保路径别名正确解析
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      '@': path.resolve(__dirname, './src'),
    };
    return config;
  },
};

export default nextConfig;
