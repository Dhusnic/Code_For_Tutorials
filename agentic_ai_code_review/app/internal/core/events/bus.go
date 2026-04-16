package events

import (
	"context"
	"sync"
	"time"
)

type Event struct {
	Type      string         `json:"type"`
	Timestamp int64          `json:"timestamp"`
	Payload   map[string]any `json:"payload,omitempty"`
}

type Bus struct {
	mu          sync.RWMutex
	subscribers map[string]map[chan Event]struct{}
}

func NewBus() *Bus {
	return &Bus{
		subscribers: make(map[string]map[chan Event]struct{}),
	}
}

func (b *Bus) Subscribe(eventType string, bufferSize int) (<-chan Event, func()) {
	if bufferSize < 1 {
		bufferSize = 1
	}
	ch := make(chan Event, bufferSize)

	b.mu.Lock()
	if _, ok := b.subscribers[eventType]; !ok {
		b.subscribers[eventType] = make(map[chan Event]struct{})
	}
	b.subscribers[eventType][ch] = struct{}{}
	b.mu.Unlock()

	cancel := func() {
		b.mu.Lock()
		defer b.mu.Unlock()
		if group, ok := b.subscribers[eventType]; ok {
			delete(group, ch)
			if len(group) == 0 {
				delete(b.subscribers, eventType)
			}
		}
		close(ch)
	}
	return ch, cancel
}

func (b *Bus) Publish(eventType string, payload map[string]any) {
	b.mu.RLock()
	targets := make([]chan Event, 0, len(b.subscribers[eventType]))
	for ch := range b.subscribers[eventType] {
		targets = append(targets, ch)
	}
	b.mu.RUnlock()

	event := Event{
		Type:      eventType,
		Timestamp: time.Now().Unix(),
		Payload:   payload,
	}

	for _, ch := range targets {
		select {
		case ch <- event:
		default:
			// Drop on backpressure to keep publishers non-blocking.
		}
	}
}

func Next(ctx context.Context, ch <-chan Event) (Event, bool) {
	select {
	case <-ctx.Done():
		return Event{}, false
	case event, ok := <-ch:
		return event, ok
	}
}
