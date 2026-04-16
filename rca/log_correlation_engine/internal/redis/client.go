package redis

import (
	"log_correlation_engine/internal/config"

	goredis "github.com/redis/go-redis/v9"
)

type Client struct {
	raw *goredis.Client
}

func NewClient(cfg config.RedisConfig) *Client {
	return &Client{
		raw: goredis.NewClient(&goredis.Options{
			Addr:         cfg.Address,
			Username:     cfg.Username,
			Password:     cfg.Password,
			DB:           cfg.DB,
			DialTimeout:  cfg.DialTimeout,
			ReadTimeout:  cfg.ReadTimeout,
			WriteTimeout: cfg.WriteTimeout,
		}),
	}
}

func (c *Client) Raw() *goredis.Client {
	return c.raw
}

func (c *Client) Close() error {
	if c == nil || c.raw == nil {
		return nil
	}
	return c.raw.Close()
}
