package configevents

import (
	"context"
	"log/slog"
	"time"

	"log_correlation_engine/internal/config"

	goredis "github.com/redis/go-redis/v9"
)

func ListenRedis(ctx context.Context, client *goredis.Client, cfg config.RedisNotifyConfig, logger *slog.Logger, onChange func(context.Context, string) error) {
	if !cfg.Enabled || client == nil || onChange == nil {
		return
	}
	delay := cfg.ReconnectDelay
	if delay <= 0 {
		delay = 5 * time.Second
	}

	go func() {
		for ctx.Err() == nil {
			pubsub := client.Subscribe(ctx, cfg.Channel)
			if _, err := pubsub.Receive(ctx); err != nil {
				_ = pubsub.Close()
				if logger != nil {
					logger.Warn("failed to subscribe to config change channel", "channel", cfg.Channel, "error", err)
				}
				sleep(ctx, delay)
				continue
			}
			if logger != nil {
				logger.Info("listening for config change notifications", "channel", cfg.Channel)
			}

			for ctx.Err() == nil {
				msg, err := pubsub.ReceiveMessage(ctx)
				if err != nil {
					if logger != nil && ctx.Err() == nil {
						logger.Warn("config change listener disconnected", "channel", cfg.Channel, "error", err)
					}
					break
				}
				if err := onChange(ctx, msg.Payload); err != nil && logger != nil {
					logger.Warn("config change notification handling failed", "channel", cfg.Channel, "payload", msg.Payload, "error", err)
				}
			}
			_ = pubsub.Close()
			sleep(ctx, delay)
		}
	}()
}

func sleep(ctx context.Context, delay time.Duration) {
	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
	case <-timer.C:
	}
}
