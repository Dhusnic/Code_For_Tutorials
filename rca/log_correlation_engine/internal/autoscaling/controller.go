package autoscaling

import (
	"strings"
	"sync"
	"time"

	"log_correlation_engine/internal/config"
)

const inputBasisIncrementalLogs = "incremental_logs"

type SchedulerSettings struct {
	Interval   time.Duration
	RunTimeout time.Duration
}

type OrganizationSettings struct {
	GroupedLookupBatchSize int
	MaxNewLogsPerCycle     int
}

type Controller struct {
	enabled        bool
	inputBasis     string
	lowWatermark   int
	highWatermark  int
	cooldownCycles int

	staticScheduler SchedulerSettings
	staticBatchSize int

	schedulerMinInterval  time.Duration
	schedulerMaxInterval  time.Duration
	schedulerTimeoutRatio float64

	fetcherMinBatchSize int
	fetcherMaxBatchSize int
	maxBatchesPerCycle  int

	mu        sync.Mutex
	warmed    bool
	scheduler schedulerState
	orgs      map[string]*organizationState
}

type schedulerState struct {
	currentInterval time.Duration
	downCycles      int
}

type organizationState struct {
	currentBatchSize int
	downCycles       int
}

func NewController(cfg config.AutoscalingConfig, staticScheduler SchedulerSettings, staticBatchSize int) *Controller {
	controller := &Controller{
		enabled:               cfg.Enabled,
		inputBasis:            strings.ToLower(strings.TrimSpace(cfg.InputBasis)),
		lowWatermark:          cfg.InputLowWatermark,
		highWatermark:         cfg.InputHighWatermark,
		cooldownCycles:        cfg.ScaleDownCooldownCycles,
		staticScheduler:       sanitizeSchedulerSettings(staticScheduler),
		staticBatchSize:       maxInt(1, staticBatchSize),
		schedulerMinInterval:  cfg.Scheduler.MinInterval,
		schedulerMaxInterval:  cfg.Scheduler.MaxInterval,
		schedulerTimeoutRatio: cfg.Scheduler.TimeoutRatio,
		fetcherMinBatchSize:   cfg.Fetcher.MinGroupedLookupBatchSize,
		fetcherMaxBatchSize:   cfg.Fetcher.MaxGroupedLookupBatchSize,
		maxBatchesPerCycle:    maxInt(1, cfg.Fetcher.MaxBatchesPerCycle),
		orgs:                  make(map[string]*organizationState),
	}
	controller.scheduler.currentInterval = controller.staticScheduler.Interval
	if controller.inputBasis == "" {
		controller.inputBasis = inputBasisIncrementalLogs
	}
	return controller
}

func (c *Controller) Enabled() bool {
	return c != nil && c.enabled
}

func (c *Controller) CurrentSchedulerSettings() SchedulerSettings {
	if c == nil {
		return SchedulerSettings{}
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	settings := c.staticScheduler
	if c.enabled && c.warmed {
		if c.scheduler.currentInterval > 0 {
			settings.Interval = c.scheduler.currentInterval
		}
		settings.RunTimeout = time.Duration(float64(settings.Interval) * c.schedulerTimeoutRatio)
	}
	return sanitizeSchedulerSettings(settings)
}

func (c *Controller) ObserveCycle(totalIncrementalLogs int) {
	if c == nil || !c.enabled || c.inputBasis != inputBasisIncrementalLogs {
		return
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	targetInterval := c.resolveSchedulerInterval(totalIncrementalLogs)
	if c.scheduler.currentInterval <= 0 {
		c.scheduler.currentInterval = c.staticScheduler.Interval
	}
	c.scheduler.currentInterval, c.scheduler.downCycles = applyCooldownDuration(
		c.scheduler.currentInterval,
		targetInterval,
		c.scheduler.downCycles,
		c.cooldownCycles,
	)
	c.warmed = true
}

func (c *Controller) ResolveOrganization(organization string, incrementalCount int) OrganizationSettings {
	if c == nil {
		return OrganizationSettings{}
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	batchSize := c.staticBatchSize
	if c.enabled && c.warmed && c.inputBasis == inputBasisIncrementalLogs {
		state, ok := c.orgs[organization]
		if !ok {
			state = &organizationState{currentBatchSize: c.staticBatchSize}
			c.orgs[organization] = state
		}

		targetBatchSize := c.scaleInt(incrementalCount, c.fetcherMinBatchSize, c.fetcherMaxBatchSize)
		if state.currentBatchSize <= 0 {
			state.currentBatchSize = c.staticBatchSize
		}
		state.currentBatchSize, state.downCycles = applyCooldownInt(
			state.currentBatchSize,
			targetBatchSize,
			state.downCycles,
			c.cooldownCycles,
		)
		batchSize = state.currentBatchSize
	}

	result := OrganizationSettings{
		GroupedLookupBatchSize: maxInt(1, batchSize),
	}
	if c.enabled {
		result.MaxNewLogsPerCycle = result.GroupedLookupBatchSize * c.maxBatchesPerCycle
	}
	return result
}

func sanitizeSchedulerSettings(settings SchedulerSettings) SchedulerSettings {
	if settings.Interval <= 0 {
		settings.Interval = time.Second
	}
	if settings.RunTimeout <= 0 || settings.RunTimeout > settings.Interval {
		settings.RunTimeout = settings.Interval
	}
	return settings
}

func applyCooldownInt(current, target, downCycles, cooldownCycles int) (int, int) {
	current = maxInt(1, current)
	target = maxInt(1, target)
	if target > current {
		return target, 0
	}
	if target == current {
		return current, 0
	}
	downCycles++
	if downCycles >= maxInt(1, cooldownCycles) {
		return target, 0
	}
	return current, downCycles
}

func applyCooldownDuration(current, target time.Duration, downCycles, cooldownCycles int) (time.Duration, int) {
	if current <= 0 {
		current = time.Second
	}
	if target <= 0 {
		target = time.Second
	}
	if target > current {
		return target, 0
	}
	if target == current {
		return current, 0
	}
	downCycles++
	if downCycles >= maxInt(1, cooldownCycles) {
		return target, 0
	}
	return current, downCycles
}

func (c *Controller) scaleInt(input, minimum, maximum int) int {
	minimum = maxInt(1, minimum)
	maximum = maxInt(minimum, maximum)
	if input <= c.lowWatermark {
		return minimum
	}
	if input >= c.highWatermark {
		return maximum
	}
	if c.highWatermark <= c.lowWatermark {
		return maximum
	}

	ratio := float64(input-c.lowWatermark) / float64(c.highWatermark-c.lowWatermark)
	value := float64(minimum) + ratio*float64(maximum-minimum)
	return int(value + 0.5)
}

func (c *Controller) scaleDuration(input int, minimum, maximum time.Duration) time.Duration {
	if minimum <= 0 {
		minimum = time.Second
	}
	if maximum < minimum {
		maximum = minimum
	}
	if input <= c.lowWatermark {
		return minimum
	}
	if input >= c.highWatermark {
		return maximum
	}
	if c.highWatermark <= c.lowWatermark {
		return maximum
	}

	ratio := float64(input-c.lowWatermark) / float64(c.highWatermark-c.lowWatermark)
	value := float64(minimum) + ratio*float64(maximum-minimum)
	return time.Duration(value)
}

func (c *Controller) resolveSchedulerInterval(totalIncrementalLogs int) time.Duration {
	if totalIncrementalLogs <= 0 {
		return c.schedulerMinInterval
	}

	// Keep the scheduler pinned at the minimum interval while the fetch side
	// can still absorb the observed backlog by growing grouped lookup batches.
	maxBatchCapacityAtMinInterval := c.fetcherMaxBatchSize * c.maxBatchesPerCycle
	if maxBatchCapacityAtMinInterval <= 0 || totalIncrementalLogs <= maxBatchCapacityAtMinInterval {
		return c.schedulerMinInterval
	}

	intervalFactor := float64(c.schedulerMaxInterval) / float64(c.schedulerMinInterval)
	if intervalFactor < 1 {
		intervalFactor = 1
	}
	upperBound := int(float64(maxBatchCapacityAtMinInterval) * intervalFactor)
	if upperBound <= maxBatchCapacityAtMinInterval {
		upperBound = maxBatchCapacityAtMinInterval + 1
	}

	if totalIncrementalLogs >= upperBound {
		return c.schedulerMaxInterval
	}

	ratio := float64(totalIncrementalLogs-maxBatchCapacityAtMinInterval) / float64(upperBound-maxBatchCapacityAtMinInterval)
	value := float64(c.schedulerMinInterval) + ratio*float64(c.schedulerMaxInterval-c.schedulerMinInterval)
	return time.Duration(value)
}

func maxInt(left, right int) int {
	if left > right {
		return left
	}
	return right
}
