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

type DistributedObservation struct {
	ActiveWorkers        int
	CorrelationWorkUnits int
	PlannedShards        int
	CompletedShards      int
	RetryCount           int
	QueueDepth           int
	TotalShardDuration   time.Duration
	MaxShardDuration     time.Duration
	MergeDuration        time.Duration
}

type DistributedShardHints struct {
	DefaultTargetLogsPerShard int
	MinShardsPerWorker        int
	MaxShardsPerWorker        int
	TargetShardDuration       time.Duration
}

type DistributedShardPlan struct {
	ActiveWorkers            int
	DesiredShards            int
	TargetLogsPerShard       int
	QueueDepth               int
	EstimatedClusterDuration time.Duration
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

	mu          sync.Mutex
	warmed      bool
	scheduler   schedulerState
	distributed clusterState
	orgs        map[string]*organizationState
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

type clusterState struct {
	activeWorkers       int
	hasObservation      bool
	lastObservation     DistributedObservation
	perWorkerThroughput float64
	workUnitMultiplier  float64
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
	controller.distributed.activeWorkers = 1
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

func (c *Controller) ObserveDistributedCycle(totalIncrementalLogs int, activeWorkers int) {
	if c == nil || !c.enabled || c.inputBasis != inputBasisIncrementalLogs {
		return
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	c.scheduler.lastWorkload = maxInt(0, totalIncrementalLogs)
	c.scheduler.hasWorkload = true
	c.distributed.activeWorkers = maxInt(1, activeWorkers)
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

func (c *Controller) ObserveDistributedObservation(observation DistributedObservation) {
	if c == nil || !c.enabled {
		return
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	sanitized := sanitizeDistributedObservation(observation)
	if sanitized.ActiveWorkers > 0 {
		c.distributed.activeWorkers = sanitized.ActiveWorkers
	}
	if sanitized.CorrelationWorkUnits > 0 && sanitized.TotalShardDuration > 0 {
		target := float64(sanitized.CorrelationWorkUnits) / sanitized.TotalShardDuration.Seconds()
		c.distributed.perWorkerThroughput = blendPositiveFloat(c.distributed.perWorkerThroughput, target)
	}
	if sanitized.CorrelationWorkUnits > 0 && c.scheduler.hasWorkload && c.scheduler.lastWorkload > 0 {
		target := float64(sanitized.CorrelationWorkUnits) / float64(c.scheduler.lastWorkload)
		c.distributed.workUnitMultiplier = blendPositiveFloat(c.distributed.workUnitMultiplier, target)
	}
	c.distributed.lastObservation = sanitized
	c.distributed.hasObservation = true
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

func (c *Controller) ResolveDistributedShardPlan(
	logCount int,
	activeWorkers int,
	hints DistributedShardHints,
) DistributedShardPlan {
	activeWorkers = maxInt(1, activeWorkers)
	defaultTarget := maxInt(1, hints.DefaultTargetLogsPerShard)
	if logCount <= 0 {
		return DistributedShardPlan{
			ActiveWorkers:      activeWorkers,
			DesiredShards:      0,
			TargetLogsPerShard: defaultTarget,
		}
	}

	c.mu.Lock()
	throughput := c.distributed.perWorkerThroughput
	c.mu.Unlock()

	targetLogsPerShard := defaultTarget
	if throughput > 0 && hints.TargetShardDuration > 0 {
		targetByDuration := int(throughput*hints.TargetShardDuration.Seconds() + 0.5)
		if targetByDuration > 0 {
			targetLogsPerShard = targetByDuration
		}
	}

	baseShards := divideRoundUp(logCount, targetLogsPerShard)
	minShards := activeWorkers * maxInt(1, hints.MinShardsPerWorker)
	maxShards := activeWorkers * maxInt(maxInt(1, hints.MinShardsPerWorker), hints.MaxShardsPerWorker)
	desiredShards := clampInt(baseShards, minShards, maxShards)
	if desiredShards > logCount {
		desiredShards = logCount
	}
	if desiredShards <= 0 {
		desiredShards = 1
	}
	targetLogsPerShard = divideRoundUp(logCount, desiredShards)

	concurrentWorkers := minInt(activeWorkers, desiredShards)
	estimatedDuration := time.Duration(0)
	if throughput > 0 && concurrentWorkers > 0 {
		seconds := float64(logCount) / (throughput * float64(concurrentWorkers))
		estimatedDuration = time.Duration(seconds*float64(time.Second) + 0.5)
	}

	return DistributedShardPlan{
		ActiveWorkers:            activeWorkers,
		DesiredShards:            desiredShards,
		TargetLogsPerShard:       maxInt(1, targetLogsPerShard),
		QueueDepth:               maxInt(0, desiredShards-activeWorkers),
		EstimatedClusterDuration: estimatedDuration,
	}
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

func sanitizeDistributedObservation(observation DistributedObservation) DistributedObservation {
	observation.ActiveWorkers = maxInt(1, observation.ActiveWorkers)
	observation.CorrelationWorkUnits = maxInt(0, observation.CorrelationWorkUnits)
	observation.PlannedShards = maxInt(0, observation.PlannedShards)
	observation.CompletedShards = maxInt(0, observation.CompletedShards)
	observation.RetryCount = maxInt(0, observation.RetryCount)
	observation.QueueDepth = maxInt(0, observation.QueueDepth)
	if observation.TotalShardDuration < 0 {
		observation.TotalShardDuration = 0
	}
	if observation.MaxShardDuration < 0 {
		observation.MaxShardDuration = 0
	}
	if observation.MergeDuration < 0 {
		observation.MergeDuration = 0
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
	return c.resolveSchedulerIntervalFromDuration(observation.Duration, observation.TimedOut)
}

func (c *Controller) resolveSchedulerIntervalFromCluster() time.Duration {
	if !c.distributed.hasObservation || c.distributed.perWorkerThroughput <= 0 || !c.scheduler.hasWorkload || c.scheduler.lastWorkload <= 0 {
		return 0
	}

	activeWorkers := maxInt(1, c.distributed.activeWorkers)
	workMultiplier := c.distributed.workUnitMultiplier
	if workMultiplier <= 0 {
		workMultiplier = 1
	}

	workUnits := float64(c.scheduler.lastWorkload) * workMultiplier
	durationSeconds := workUnits / (c.distributed.perWorkerThroughput * float64(activeWorkers))
	if durationSeconds <= 0 {
		return 0
	}

	requiredDuration := time.Duration(durationSeconds*float64(time.Second) + 0.5)
	if c.distributed.lastObservation.MergeDuration > 0 {
		requiredDuration += c.distributed.lastObservation.MergeDuration
	}
	if c.distributed.lastObservation.RetryCount > 0 {
		planned := maxInt(1, c.distributed.lastObservation.PlannedShards)
		retryFactor := 1 + minFloat(1, float64(c.distributed.lastObservation.RetryCount)/float64(planned))*0.25
		requiredDuration = time.Duration(float64(requiredDuration)*retryFactor + 0.5)
	}

	return c.resolveSchedulerIntervalFromDuration(requiredDuration, false)
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
	clusterTarget := c.resolveSchedulerIntervalFromCluster()
	if clusterTarget > targetInterval {
		targetInterval = clusterTarget
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

func blendPositiveFloat(current, target float64) float64 {
	if target <= 0 {
		return current
	}
	if current <= 0 {
		return target
	}
	return current*0.5 + target*0.5
}

func divideRoundUp(value, divisor int) int {
	if divisor <= 0 {
		divisor = 1
	}
	if value <= 0 {
		return 0
	}
	return (value + divisor - 1) / divisor
}

func maxInt(left, right int) int {
	if left > right {
		return left
	}
	return right
}

func minInt(left, right int) int {
	if left < right {
		return left
	}
	return right
}

func clampInt(value, minimum, maximum int) int {
	if minimum <= 0 {
		minimum = 1
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

func minFloat(left, right float64) float64 {
	if left < right {
		return left
	}
	return right
}
