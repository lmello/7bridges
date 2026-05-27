module.exports = {
  apps: [{
    name: '7bridges',
    cwd: __dirname,
    script: '.venv/bin/python',
    args: '-m uvicorn seven_bridges.main:app --host 0.0.0.0 --port 4001',
    exec_interpreter: 'none',
    out_file: 'logs/out.log',
    error_file: 'logs/err.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
    merge_logs: true,
    autorestart: true,
    max_restarts: 10,
    min_uptime: '10s',
    restart_delay: 5000,
    max_memory_restart: '512M',
    watch: false,
    // Note: BRIDGE_DEBUG is intentionally NOT set here.
    // Debug mode disables streaming (buffers the full response),
    // which makes Kimi and other backends feel very slow.
    // Use `make run-debug` when you actually need request/response logging.
    env: {
      PYTHONPATH: 'src',
    },
  }]
};
