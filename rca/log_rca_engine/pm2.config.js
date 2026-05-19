const logRcaInstances = Number(process.env.LOG_RCA_INSTANCES || process.env.RCA_ENGINE_INSTANCES || 1);

module.exports = {
  apps: [
    {
      name: 'log-rca-engine',
      cwd: '.',
      script: './bin/log-rca-engine.exe',
      args: ['--config', './config/config.yml'],
      instances: logRcaInstances,
      exec_mode: 'fork',
      instance_var: 'RCA_WORKER_ID',
      exec_interpreter: 'none',
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      combine_logs: true,
      out_file: './logs/log-rca-engine.out.log',
      error_file: './logs/log-rca-engine.err.log',
      env: {
        PM2_APP_NAME: 'log-rca-engine',
        RCA_WORKER_COUNT: String(logRcaInstances)
      }
    }
  ]
};
