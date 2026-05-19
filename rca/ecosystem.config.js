const signalizingInstances = Number(process.env.SIGNALIZING_INSTANCES || 10);
const signalizingModulePartitions = signalizingInstances;
const correlationInstances = Number(process.env.CORRELATION_INSTANCES || 10);
const logRcaInstances = Number(process.env.LOG_RCA_INSTANCES || process.env.RCA_ENGINE_INSTANCES || 10);

const directStreamApps = [
  {
    name: 'signalizing-engine',
    cwd: './log_signalizing/signalizing_go',
    script: './bin/signalizing-engine.exe',
    args: ['--config', '../config.yml'],
    instances: signalizingInstances,
    exec_mode: 'fork',
    instance_var: 'RCA_WORKER_ID',
    exec_interpreter: 'none',
    autorestart: true,
    max_restarts: 5,
    restart_delay: 5000,
    combine_logs: true,
    out_file: './logs/signalizing-engine.out.log',
    error_file: './logs/signalizing-engine.err.log',
    env: {
      PM2_APP_NAME: 'signalizing-engine',
      RCA_WORKER_COUNT: String(signalizingModulePartitions)
    }
  },
  {
    name: 'log-config-syncer',
    cwd: './log_rca_engine',
    script: './bin/log-config-syncer.exe',
    args: ['--config', './config/config.yml', '--interval', '30s'],
    instances: 1,
    exec_mode: 'fork',
    exec_interpreter: 'none',
    autorestart: true,
    max_restarts: 10,
    restart_delay: 5000,
    combine_logs: true,
    out_file: './logs/log-config-syncer.out.log',
    error_file: './logs/log-config-syncer.err.log',
    env: {
      PM2_APP_NAME: 'log-config-syncer'
    }
  },
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
];

const compatibilityCollectorApp = {
  name: 'signaled-logs-collector',
  cwd: './log_signal_processor',
  script: './bin/signaled-logs-collector.exe',
  args: ['--config', './config.yml'],
  instances: 2,
  exec_mode: 'fork',
  instance_var: 'SLP_PM2_INSTANCE_ID',
  exec_interpreter: 'none',
  autorestart: true,
  max_restarts: 10,
  restart_delay: 5000,
  combine_logs: true,
  out_file: './logs/signaled-logs-collector.out.log',
  error_file: './logs/signaled-logs-collector.err.log',
  env: {
    PM2_APP_NAME: 'signaled-logs-collector',
    SLP_PM2_APP_NAME: 'signaled-logs-collector',
    SLP_PM2_INSTANCES: '2'
  }
};

module.exports = {
  // Default stack:
  // raw logs -> signalizing-engine -> Redis stream -> correlation-engine -> Elasticsearch RCA results -> log-rca-engine
  apps: directStreamApps,

  // Optional compatibility app definition if you still want the legacy
  // Elasticsearch -> signaled-logs-collector -> Redis hash path during migration.
  optionalApps: [compatibilityCollectorApp]
};
