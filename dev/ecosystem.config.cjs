/**
 * PM2 ecosystem file for ccBitTorrent daemon (and optional client/TUI).
 *
 * Prerequisites:
 *   - Node.js and PM2 installed: npm install -g pm2
 *   - Project deps installed: uv sync (or pip install -e .)
 *
 * Usage:
 *   pm2 start ecosystem.config.cjs
 *   pm2 start ecosystem.config.cjs --only ccbt-daemon
 *   pm2 logs ccbt-daemon
 *   pm2 stop ccbt-daemon
 *
 * Logs (when using this file):
 *   - Daemon: logs/pm2/ccbt-daemon-out.log, ccbt-daemon-error.log
 *   - Interface (dashboard): logs/pm2/ccbt-dashboard-out.log, ccbt-dashboard-error.log
 *   - App-level daemon logs: ~/.ccbt/daemon/daemon_startup.log (first startup only)
 *   - Optional observability logs: ~/.ccbt/logs/ (if log_file set in config)
 */

const path = require("path");

const projectRoot = path.resolve(__dirname);
const isWindows = process.platform === "win32";
const pythonExe = isWindows
  ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
  : path.join(projectRoot, ".venv", "bin", "python");
const logDir = path.join(projectRoot, "logs", "pm2");

module.exports = {
  apps: [
    {
      name: "ccbt-daemon",
      script: path.join(projectRoot, "dev", "run_daemon_pm2.py"),
      interpreter: pythonExe,
      cwd: projectRoot,
      args: [], // e.g. ["--config", "ccbt.toml"]
      instances: 1,
      autorestart: true,
      watch: false,
      max_restarts: 10,
      min_uptime: "5s",
      out_file: path.join(logDir, "ccbt-daemon-out.log"),
      error_file: path.join(logDir, "ccbt-daemon-error.log"),
      log_date_format: "YYYY-MM-DD HH:mm:ss.SSS",
      merge_logs: true,
      env: {},
    },
    {
      name: "ccbt-dashboard",
      script: path.join(projectRoot, "dev", "run_dashboard_pm2.py"),
      interpreter: pythonExe,
      cwd: projectRoot,
      args: [], // e.g. ["--refresh", "2.0"]
      instances: 1,
      autorestart: true,
      watch: false,
      max_restarts: 10,
      min_uptime: "5s",
      out_file: path.join(logDir, "ccbt-dashboard-out.log"),
      error_file: path.join(logDir, "ccbt-dashboard-error.log"),
      log_date_format: "YYYY-MM-DD HH:mm:ss.SSS",
      merge_logs: true,
      env: {},
    },
  ],
};
