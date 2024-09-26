
```
infraon_backend_api
├── .dockerignore
├── .gitignore
├── agent_manager_app.json
├── common
│   ├── config
│   │   ├── app.config.js
│   │   ├── default_modeldata.config.js
│   │   ├── env.config.ci.js
│   │   ├── env.config.docker.js
│   │   └── env.config.js
│   ├── middlewares
│   │   ├── auth.permission.middleware.js
│   │   └── auth.validation.middleware.js
│   ├── services
│   │   ├── kafka.service.js
│   │   ├── logger.service.js
│   │   ├── mongoose.service.js
│   │   ├── rabbitmq.service.js
│   │   ├── redis.service.js
│   │   └── snowflake.service.js
│   └── utility.js
├── docker-compose.yml
├── Dockerfile
├── ecosystem.config.js
├── infraon.buildinfo
├── install_server.sh
├── logs
│   ├── .28316c48450b4eb9390db42349d7617f9d649414-audit.json
│   ├── .8093bd32371468d1fbaf092a3bc6a6c38ae95c41-audit.json
│   ├── .f6436e2516696352aa44d23cbf40b714d1550578-audit.json
│   ├── .ffbefbf271b83e41652f8b22abdbd321468940e6-audit.json
│   ├── agentlog_info_2024-09-10.log
│   ├── agentlog_info_2024-09-12.log
│   ├── agentlog_info_2024-09-13.log
│   ├── agentlog_info_2024-09-15.log
│   ├── agentlog_info_2024-09-17.log
│   ├── app_info_2024-08-06.log.gz
│   ├── app_info_2024-09-10.log
│   ├── app_info_2024-09-12.log
│   ├── app_info_2024-09-13.log
│   ├── app_info_2024-09-15.log
│   └── app_info_2024-09-17.log
├── log_proxy_server.js
├── media
│   └── agents
│       └── base
│           ├── mac
│           │   └── releases
│           │       ├── arm
│           │       │   ├── infraonagent__latest.zip
│           │       │   └── version.dat
│           │       └── intel
│           │           ├── infraonagent__latest.zip
│           │           └── version.dat
│           └── windows
│               └── releases
│                   ├── infraonwindowsagent__latest.zip
│                   └── version.dat
├── modules
│   ├── agent
│   │   ├── controllers
│   │   │   └── agent.controller.js
│   │   ├── models
│   │   │   └── agent.model.js
│   │   ├── routes.config.js
│   │   └── tasks
│   │       └── process_recvd_data.task.js
│   ├── authorization
│   │   ├── controllers
│   │   │   └── authorization.controller.js
│   │   ├── middlewares
│   │   │   └── verify.agent.middleware.js
│   │   └── routes.config.js
│   └── users
│       ├── controllers
│       │   └── users.controller.js
│       ├── models
│       │   └── users.model.js
│       └── routes.config.js
├── package-lock.json
├── package.json
├── README.md
├── routes.config.js
├── runserver.bat
├── server.js
├── server.sh
├── ssl
│   └── self_signed_cert_steps.txt
├── tasks
│   ├── index.js
│   ├── purge_queue.js
│   ├── push_os_images.js
│   └── reprocess_queue.js
├── tutorial.md
├── webpack.config.js
└── websocket
    ├── client1.js
    ├── client2.js
    ├── handlers
    │   ├── agent-datasync-handler.js
    │   ├── handlers.js
    │   ├── msgexchange-handler.js
    │   └── queue-handler.js
    ├── helper.js
    └── index.js

```

