const correlationInstances = Number(process.env.CORRELATION_INSTANCES || 1);
const logRcaInstances = Number(process.env.LOG_RCA_INSTANCES || 1);

module.exports = {
  apps: [
    {
      name: 'correlation-engine',
      cwd: './log_correlation_engine',
      script: './bin/correlation-engine.exe',
      args: ['--config', './config/config.yml'],
      instances: correlationInstances,
      exec_mode: 'fork',
      instance_var: 'RCA_WORKER_ID',
      exec_interpreter: 'none',
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      combine_logs: true,
      out_file: './logs/correlation-engine.out.log',
      error_file: './logs/correlation-engine.err.log',
      env: {
        PM2_APP_NAME: 'correlation-engine'
      }
    },
    {
      name: 'log-rca-engine',
      cwd: './log_rca_engine',
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
