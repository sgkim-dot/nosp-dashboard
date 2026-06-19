// PM2 process manager config for the dashboard dev server.
// Use: pm2 start ecosystem.config.cjs   (from apps/dashboard)
// Goal: dashboard on :3100 stays alive no matter what happens to any terminal.
module.exports = {
  apps: [
    {
      name: "dashboard-3100",
      script: "node_modules/next/dist/bin/next",
      args: "dev --turbopack -p 3100",
      cwd: __dirname,
      env: {
        NODE_ENV: "development",
        NEXT_DIST_DIR: ".next-3100",
      },
      autorestart: true,
      max_restarts: 50,
      min_uptime: "10s",
      restart_delay: 2000,
      watch: false,
      max_memory_restart: "2G",
      out_file: "./.pm2/out.log",
      error_file: "./.pm2/err.log",
      merge_logs: true,
      time: true,
    },
  ],
};
