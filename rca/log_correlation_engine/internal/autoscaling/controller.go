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

type ExecutionObservation struct {
	Interval   time.Duration
	RunTimeout time.Duration
	Duration   time.Duration
	Failed     bool
	TimedOut   bool
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

	schedulerMinInterval          time.Duration
	schedulerMaxInterval          time.Duration
	schedulerTimeoutRatio         float64
	schedulerTargetUtilization    float64
	schedulerTimeoutScaleUpFactor float64

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
	lastWorkload    int
	hasWorkload     bool
	lastExecution   ExecutionObservation
	hasExecution    bool
}

type organizationState struct {
	currentBatchSize int
	downCycles       int
}

func NewController(cfg config.AutoscalingConfig, staticScheduler SchedulerSettings, staticBatchSize int) *Controller {
	controller := &Controller{
		enabled:                       cfg.Enabled,
		inputBasis:                    strings.ToLower(strings.TrimSpace(cfg.InputBasis)),
		lowWatermark:                  cfg.InputLowWatermark,
		highWatermark:                 cfg.InputHighWatermark,
		cooldownCycles:                cfg.ScaleDownCooldownCycles,
		staticScheduler:               sanitizeSchedulerSettings(staticScheduler),
		staticBatchSize:               maxInt(1, staticBatchSize),
		schedulerMinInterval:          cfg.Scheduler.MinInterval,
		schedulerMaxInterval:          cfg.Scheduler.MaxInterval,
		schedulerTimeoutRatio:         cfg.Scheduler.TimeoutRatio,
		schedulerTargetUtilization:    cfg.Scheduler.TargetCycleUtilization,
		schedulerTimeoutScaleUpFactor: cfg.Scheduler.TimeoutScaleUpMultiplier,
		fetcherMinBatchSize:           cfg.Fetcher.MinGroupedLookupBatchSize,
		fetcherMaxBatchSize:           cfg.Fetcher.MaxGroupedLookupBatchSize,
		maxBatchesPerCycle:            maxInt(1, cfg.Fetcher.MaxBatchesPerCycle),
		orgs:                          make(map[string]*organizationState),
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

	c.scheduler.lastWorkload = maxInt(0, totalIncrementalLogs)
	c.scheduler.hasWorkload = true
	c.recomputeSchedulerLocked()
}

func (c *Controller) ObserveExecution(observation ExecutionObservation) {
	if c == nil || !c.enabled {
		return
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	c.scheduler.lastExecution = sanitizeExecutionObservation(observation)
	c.scheduler.hasExecution = true
	c.recomputeSchedulerLocked()
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

func sanitizeExecutionObservation(observation ExecutionObservation) ExecutionObservation {
	if observation.Interval <= 0 {
		observation.Interval = time.Second
	}
	if observation.RunTimeout <= 0 || observation.RunTimeout > observation.Interval {
		observation.RunTimeout = observation.Interval
	}
	if observation.Duration < 0 {
		observation.Duration = 0
	}
	return observation
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
	return time.Duration(value + 0.5)
}

func (c *Controller) resolveSchedulerIntervalFromExecution(observation ExecutionObservation) time.Duration {
	if observation.Duration <= 0 {
		return 0
	}
	if observation.Failed && !observation.TimedOut {
		return 0
	}

	targetUtilization := c.schedulerTargetUtilization
	if targetUtilization <= 0 || targetUtilization >= 1 {
		targetUtilization = 0.8
	}
	timeoutRatio := c.schedulerTimeoutRatio
	if timeoutRatio <= 0 || timeoutRatio >= 1 {
		timeoutRatio = 0.9
	}

	requiredInterval := float64(observation.Duration) / (timeoutRatio * targetUtilization)
	if observation.TimedOut {
		scaleUpFactor := c.schedulerTimeoutScaleUpFactor
		if scaleUpFactor < 1 {
			scaleUpFactor = 1
		}
		requiredInterval *= scaleUpFactor
	}

	return clampDuration(
		time.Duration(requiredInterval+0.5),
		c.schedulerMinInterval,
		c.schedulerMaxInterval,
	)
}

func (c *Controller) recomputeSchedulerLocked() {
	targetInterval := time.Duration(0)
	if c.scheduler.hasWorkload {
		targetInterval = c.resolveSchedulerInterval(c.scheduler.lastWorkload)
	}
	if c.scheduler.hasExecution {
		executionTarget := c.resolveSchedulerIntervalFromExecution(c.scheduler.lastExecution)
		if executionTarget > targetInterval {
			targetInterval = executionTarget
		}
	}
	if targetInterval <= 0 {
		return
	}
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

func maxInt(left, right int) int {
	if left > right {
		return left
	}
	return right
}

func clampDuration(value, minimum, maximum time.Duration) time.Duration {
	if minimum <= 0 {
		minimum = time.Second
	}
	if maximum < minimum {
		maximum = minimum
	}
	if value < minimum {
		return minimum
	}
	if value > maximum {
		return maximum
	}
	return value
}
