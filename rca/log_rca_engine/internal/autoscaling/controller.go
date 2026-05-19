package autoscaling

import (
	"sync"
	"time"

	"log_rca_engine/internal/config"
)

const inputBasisCorrelationEvents = "correlation_events"

type SchedulerSettings struct {
	Interval   time.Duration
	RunTimeout time.Duration
}

type ReaderSettings struct {
	PageSize         int
	MaxPagesPerCycle int
}

type ExecutionObservation struct {
	Interval   time.Duration
	RunTimeout time.Duration
	Duration   time.Duration
	Failed     bool
	TimedOut   bool
}

type Controller struct {
	enabled        bool
	inputBasis     string
	lowWatermark   int
	highWatermark  int
	cooldownCycles int

	staticScheduler SchedulerSettings
	staticPageSize  int
	staticMaxPages  int

	schedulerMinInterval          time.Duration
	schedulerMaxInterval          time.Duration
	schedulerTimeoutRatio         float64
	schedulerTargetUtilization    float64
	schedulerTimeoutScaleUpFactor float64

	readerMinPageSize int
	readerMaxPageSize int

	mu        sync.Mutex
	warmed    bool
	scheduler schedulerState
	reader    readerState
}

type schedulerState struct {
	currentInterval time.Duration
	downCycles      int
	lastWorkload    int
	hasWorkload     bool
	lastExecution   ExecutionObservation
	hasExecution    bool
}

type readerState struct {
	currentPageSize int
	downCycles      int
}

func NewController(
	cfg config.AutoscalingConfig,
	staticScheduler SchedulerSettings,
	staticReader ReaderSettings,
) *Controller {
	controller := &Controller{
		enabled:                       cfg.Enabled,
		inputBasis:                    cfg.InputBasis,
		lowWatermark:                  cfg.InputLowWatermark,
		highWatermark:                 cfg.InputHighWatermark,
		cooldownCycles:                cfg.ScaleDownCooldownCycles,
		staticScheduler:               sanitizeSchedulerSettings(staticScheduler),
		staticPageSize:                maxInt(1, staticReader.PageSize),
		staticMaxPages:                maxInt(1, staticReader.MaxPagesPerCycle),
		schedulerMinInterval:          cfg.Scheduler.MinInterval,
		schedulerMaxInterval:          cfg.Scheduler.MaxInterval,
		schedulerTimeoutRatio:         cfg.Scheduler.TimeoutRatio,
		schedulerTargetUtilization:    cfg.Scheduler.TargetCycleUtilization,
		schedulerTimeoutScaleUpFactor: cfg.Scheduler.TimeoutScaleUpMultiplier,
		readerMinPageSize:             cfg.Reader.MinPageSize,
		readerMaxPageSize:             cfg.Reader.MaxPageSize,
	}
	controller.scheduler.currentInterval = controller.staticScheduler.Interval
	controller.reader.currentPageSize = controller.staticPageSize
	if controller.inputBasis == "" {
		controller.inputBasis = inputBasisCorrelationEvents
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

func (c *Controller) CurrentReaderSettings() ReaderSettings {
	if c == nil {
		return ReaderSettings{}
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	pageSize := c.staticPageSize
	if c.enabled && c.warmed && c.inputBasis == inputBasisCorrelationEvents {
		targetPageSize := c.scaleInt(c.scheduler.lastWorkload, c.readerMinPageSize, c.readerMaxPageSize)
		if c.reader.currentPageSize <= 0 {
			c.reader.currentPageSize = c.staticPageSize
		}
		c.reader.currentPageSize, c.reader.downCycles = applyCooldownInt(
			c.reader.currentPageSize,
			targetPageSize,
			c.reader.downCycles,
			c.cooldownCycles,
		)
		pageSize = c.reader.currentPageSize
	}

	return ReaderSettings{
		PageSize:         maxInt(1, pageSize),
		MaxPagesPerCycle: c.staticMaxPages,
	}
}

func (c *Controller) ObserveCycle(totalCorrelationEvents int) {
	if c == nil || !c.enabled || c.inputBasis != inputBasisCorrelationEvents {
		return
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	c.scheduler.lastWorkload = maxInt(0, totalCorrelationEvents)
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

func (c *Controller) resolveSchedulerInterval(totalCorrelationEvents int) time.Duration {
	if totalCorrelationEvents <= 0 {
		return c.schedulerMinInterval
	}

	maxCycleCapacityAtMinInterval := c.readerMaxPageSize * c.staticMaxPages
	if maxCycleCapacityAtMinInterval <= 0 || totalCorrelationEvents <= maxCycleCapacityAtMinInterval {
		return c.schedulerMinInterval
	}

	intervalFactor := float64(c.schedulerMaxInterval) / float64(c.schedulerMinInterval)
	if intervalFactor < 1 {
		intervalFactor = 1
	}
	upperBound := int(float64(maxCycleCapacityAtMinInterval) * intervalFactor)
	if upperBound <= maxCycleCapacityAtMinInterval {
		upperBound = maxCycleCapacityAtMinInterval + 1
	}

	if totalCorrelationEvents >= upperBound {
		return c.schedulerMaxInterval
	}

	ratio := float64(totalCorrelationEvents-maxCycleCapacityAtMinInterval) / float64(upperBound-maxCycleCapacityAtMinInterval)
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
	return c.resolveSchedulerIntervalFromDuration(observation.Duration, observation.TimedOut)
}

func (c *Controller) resolveSchedulerIntervalFromDuration(duration time.Duration, timedOut bool) time.Duration {
	if duration <= 0 {
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

	requiredInterval := float64(duration) / (timeoutRatio * targetUtilization)
	if timedOut {
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

func maxInt(left, right int) int {
	if left > right {
		return left
	}
	return right
}
