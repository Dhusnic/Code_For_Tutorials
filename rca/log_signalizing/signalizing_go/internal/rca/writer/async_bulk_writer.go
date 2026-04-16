package writer

import (
	"fmt"
	"sync"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"

	"rca/internal/rca/logging"
)

// FlushFunc processes one bulk action batch.
type FlushFunc func([]map[string]any) error

type queueItem struct {
	actions  []map[string]any
	sentinel bool
}

// AsyncBulkWriter processes bulk batches concurrently with bounded backpressure.
type AsyncBulkWriter struct {
	flushFn   FlushFunc
	queue     chan queueItem
	logger    logging.Logger
	mu        sync.Mutex
	firstErr  error
	closed    bool
	workerSeq int
	workers   int

	workerWG sync.WaitGroup
	workWG   sync.WaitGroup
	bgWG     sync.WaitGroup
	stopCh   chan struct{}

	autoscalingEnabled bool

	queueEnqueueTimeout time.Duration
	spoolReplayInterval time.Duration
	spool               *DiskSpoolStore

	autoscaleMinWorkers    int
	autoscaleMaxWorkers    int
	autoscaleUpRatio       float64
	autoscaleDownRatio     float64
	cpuLimitPercent        float64
	memoryLimitPercent     float64
	autoscaleCheckInterval time.Duration
	autoscaleCooldown      time.Duration
	lastScaleAt            time.Time

	resourcePressureHighFn func() bool
}

// NewAsyncBulkWriter constructs the concurrent bulk writer.
func NewAsyncBulkWriter(
	flushFn FlushFunc,
	workerCount int,
	queueSize int,
	logger logging.Logger,
	autoscalingEnabled bool,
	minWorkerCount int,
	maxWorkerCount int,
	scaleUpQueueRatio float64,
	scaleDownQueueRatio float64,
	cpuLimitPercent float64,
	memoryLimitPercent float64,
	autoscaleCheckIntervalSeconds float64,
	autoscaleCooldownSeconds float64,
	spoolEnabled bool,
	spoolDirectory string,
	spoolMaxBytes int64,
	spoolReplayIntervalSeconds float64,
	queueEnqueueTimeoutSeconds float64,
) (*AsyncBulkWriter, error) {
	if workerCount < 1 {
		workerCount = 1
	}
	if queueSize < 1 {
		queueSize = 1
	}

	writer := &AsyncBulkWriter{
		flushFn:              flushFn,
		queue:                make(chan queueItem, queueSize),
		logger:               logger,
		stopCh:               make(chan struct{}),
		autoscalingEnabled:   autoscalingEnabled,
		queueEnqueueTimeout:  durationFromSeconds(queueEnqueueTimeoutSeconds, 250*time.Millisecond),
		spoolReplayInterval:  durationFromSeconds(spoolReplayIntervalSeconds, time.Second),
		autoscaleUpRatio:     clampFloat(scaleUpQueueRatio, 0.0, 1.0),
		autoscaleDownRatio:   clampFloat(scaleDownQueueRatio, 0.0, 1.0),
		cpuLimitPercent:      clampFloat(cpuLimitPercent, 1.0, 100.0),
		memoryLimitPercent:   clampFloat(memoryLimitPercent, 1.0, 100.0),
		autoscaleCheckInterval: durationFromSeconds(autoscaleCheckIntervalSeconds, 2*time.Second),
		autoscaleCooldown:      durationFromSeconds(autoscaleCooldownSeconds, 10*time.Second),
	}

	if spoolEnabled {
		spool, err := NewDiskSpoolStore(spoolDirectory, spoolMaxBytes, logger)
		if err != nil {
			return nil, err
		}
		writer.spool = spool
	}

	if writer.autoscalingEnabled {
		if minWorkerCount < 1 {
			minWorkerCount = 1
		}
		if maxWorkerCount < minWorkerCount {
			maxWorkerCount = minWorkerCount
		}
		writer.autoscaleMinWorkers = minWorkerCount
		writer.autoscaleMaxWorkers = maxWorkerCount
	} else {
		writer.autoscaleMinWorkers = workerCount
		writer.autoscaleMaxWorkers = workerCount
	}

	if writer.autoscaleDownRatio > writer.autoscaleUpRatio {
		writer.logger.Warning(
			"bulk autoscale down ratio is above up ratio; swapping values",
			logging.F("scale_down_ratio", writer.autoscaleDownRatio),
			logging.F("scale_up_ratio", writer.autoscaleUpRatio),
		)
		writer.autoscaleUpRatio, writer.autoscaleDownRatio = writer.autoscaleDownRatio, writer.autoscaleUpRatio
	}

	initialWorkers := workerCount
	if initialWorkers < writer.autoscaleMinWorkers {
		initialWorkers = writer.autoscaleMinWorkers
	}
	if initialWorkers > writer.autoscaleMaxWorkers {
		initialWorkers = writer.autoscaleMaxWorkers
	}

	for i := 0; i < initialWorkers; i++ {
		writer.startWorker()
	}

	if writer.autoscalingEnabled && writer.autoscaleMaxWorkers > writer.autoscaleMinWorkers {
		writer.bgWG.Add(1)
		go writer.autoscalerLoop()
		writer.logger.Info(
			"Bulk writer autoscaling enabled",
			logging.F("initial_workers", initialWorkers),
			logging.F("min_workers", writer.autoscaleMinWorkers),
			logging.F("max_workers", writer.autoscaleMaxWorkers),
			logging.F("scale_up_queue_ratio", writer.autoscaleUpRatio),
			logging.F("scale_down_queue_ratio", writer.autoscaleDownRatio),
			logging.F("cpu_limit_percent", writer.cpuLimitPercent),
			logging.F("memory_limit_percent", writer.memoryLimitPercent),
			logging.F("check_interval_seconds", writer.autoscaleCheckInterval.Seconds()),
			logging.F("cooldown_seconds", writer.autoscaleCooldown.Seconds()),
		)
	}

	if writer.spool != nil {
		writer.bgWG.Add(1)
		go writer.spoolReplayerLoop()
		writer.logger.Info(
			"Bulk writer disk spool enabled",
			logging.F("spool_directory", writer.spool.Directory()),
			logging.F("spool_max_bytes", spoolMaxBytes),
			logging.F("spool_replay_interval_seconds", writer.spoolReplayInterval.Seconds()),
			logging.F("queue_enqueue_timeout_seconds", writer.queueEnqueueTimeout.Seconds()),
		)
	}

	return writer, nil
}

// Submit submits one batch, applying backpressure or spooling when needed.
func (w *AsyncBulkWriter) Submit(actions []map[string]any) error {
	if len(actions) == 0 {
		return nil
	}
	if err := w.raiseIfFailed(); err != nil {
		return err
	}

	w.mu.Lock()
	closed := w.closed
	w.mu.Unlock()
	if closed {
		return fmt.Errorf("Async bulk writer is already closed")
	}

	payload := cloneActionSlice(actions)
	if w.spool == nil {
		w.workWG.Add(1)
		w.queue <- queueItem{actions: payload}
		return w.raiseIfFailed()
	}

	w.workWG.Add(1)
	timer := time.NewTimer(w.queueEnqueueTimeout)
	defer timer.Stop()
	select {
	case w.queue <- queueItem{actions: payload}:
	case <-timer.C:
		w.workWG.Done()
		if err := w.spool.EnqueueBatch(payload); err != nil {
			return err
		}
	}
	return w.raiseIfFailed()
}

// Drain waits until queued and spooled batches are processed.
func (w *AsyncBulkWriter) Drain() error {
	for {
		w.workWG.Wait()
		if w.spool == nil || !w.spool.HasPendingBatches() {
			break
		}
		replayed, err := w.replayOneSpooledBatch(true)
		if err != nil {
			return err
		}
		if !replayed {
			break
		}
	}
	return w.raiseIfFailed()
}

// Close drains and stops the worker goroutines.
func (w *AsyncBulkWriter) Close() error {
	w.mu.Lock()
	if w.closed {
		w.mu.Unlock()
		return nil
	}
	w.closed = true
	close(w.stopCh)
	w.mu.Unlock()

	w.bgWG.Wait()
	if err := w.Drain(); err != nil {
		return err
	}

	active := w.activeWorkerCount()
	for i := 0; i < active; i++ {
		w.queue <- queueItem{sentinel: true}
	}
	w.workerWG.Wait()
	return w.raiseIfFailed()
}

func (w *AsyncBulkWriter) workerLoop() {
	defer w.workerWG.Done()
	defer func() {
		w.mu.Lock()
		w.workers--
		w.mu.Unlock()
	}()

	for item := range w.queue {
		if item.sentinel {
			return
		}

		func() {
			defer w.workWG.Done()
			defer func() {
				if recovered := recover(); recovered != nil {
					err := fmt.Errorf("%v", recovered)
					w.recordError(err)
					w.logger.Exception("Async bulk writer worker failed", err)
				}
			}()

			if err := w.flushFn(item.actions); err != nil {
				w.recordError(err)
				w.logger.Exception("Async bulk writer worker failed", err)
			}
		}()
	}
}

func (w *AsyncBulkWriter) startWorker() {
	w.mu.Lock()
	w.workers++
	w.workerSeq++
	w.mu.Unlock()

	w.workerWG.Add(1)
	go w.workerLoop()
}

func (w *AsyncBulkWriter) activeWorkerCount() int {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.workers
}

func (w *AsyncBulkWriter) autoscalerLoop() {
	defer w.bgWG.Done()

	ticker := time.NewTicker(w.autoscaleCheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-w.stopCh:
			return
		case <-ticker.C:
			if err := w.autoscaleOnce(); err != nil {
				w.logger.Exception("Bulk writer autoscaler iteration failed", err)
			}
		}
	}
}

func (w *AsyncBulkWriter) autoscaleOnce() error {
	now := time.Now()
	if !w.lastScaleAt.IsZero() && now.Sub(w.lastScaleAt) < w.autoscaleCooldown {
		return nil
	}

	maxSize := cap(w.queue)
	if maxSize <= 0 {
		return nil
	}
	queueRatio := float64(len(w.queue)) / float64(maxSize)
	activeWorkers := w.activeWorkerCount()

	if queueRatio >= w.autoscaleUpRatio && activeWorkers < w.autoscaleMaxWorkers {
		if w.resourcePressureHigh() {
			w.logger.Debug(
				"Bulk writer scale-up blocked by resource guardrail",
				logging.F("queue_ratio", queueRatio),
				logging.F("active_workers", activeWorkers),
				logging.F("max_workers", w.autoscaleMaxWorkers),
			)
			return nil
		}
		w.startWorker()
		w.lastScaleAt = now
		w.logger.Info(
			"Bulk writer scaled up",
			logging.F("queue_ratio", queueRatio),
			logging.F("active_workers", w.activeWorkerCount()),
			logging.F("max_workers", w.autoscaleMaxWorkers),
		)
		return nil
	}

	if queueRatio <= w.autoscaleDownRatio && activeWorkers > w.autoscaleMinWorkers {
		select {
		case w.queue <- queueItem{sentinel: true}:
			w.lastScaleAt = now
			w.logger.Info(
				"Bulk writer scaled down",
				logging.F("queue_ratio", queueRatio),
				logging.F("active_workers_before", activeWorkers),
				logging.F("min_workers", w.autoscaleMinWorkers),
			)
		default:
		}
	}

	return nil
}

func (w *AsyncBulkWriter) spoolReplayerLoop() {
	defer w.bgWG.Done()

	for {
		select {
		case <-w.stopCh:
			return
		default:
		}

		replayed, err := w.replayOneSpooledBatch(false)
		if err != nil {
			w.logger.Exception("Disk spool replay iteration failed", err)
			time.Sleep(w.spoolReplayInterval)
			continue
		}
		if !replayed {
			time.Sleep(w.spoolReplayInterval)
		}
	}
}

func (w *AsyncBulkWriter) replayOneSpooledBatch(block bool) (bool, error) {
	if w.spool == nil || !w.spool.HasPendingBatches() {
		return false, nil
	}

	batch, err := w.spool.DequeueOldestBatch()
	if err != nil {
		return false, err
	}
	if len(batch) == 0 {
		return false, nil
	}

	if block {
		w.workWG.Add(1)
		w.queue <- queueItem{actions: batch}
	} else {
		w.workWG.Add(1)
		timer := time.NewTimer(w.queueEnqueueTimeout)
		defer timer.Stop()
		select {
		case w.queue <- queueItem{actions: batch}:
		case <-timer.C:
			w.workWG.Done()
			if err := w.spool.EnqueueBatch(batch); err != nil {
				return false, err
			}
			return false, nil
		}
	}

	w.logger.Debug(
		"Replayed spooled bulk batch",
		logging.F("batch_actions", len(batch)),
		logging.F("spool_pending_bytes", w.spool.PendingBytes()),
	)
	return true, nil
}

func (w *AsyncBulkWriter) resourcePressureHigh() bool {
	if w.resourcePressureHighFn != nil {
		return w.resourcePressureHighFn()
	}

	cpuValues, err := cpu.Percent(0, false)
	if err != nil || len(cpuValues) == 0 {
		w.logger.Warning("Failed sampling system resources for bulk autoscaling")
		return false
	}
	memoryStats, err := mem.VirtualMemory()
	if err != nil {
		w.logger.Warning("Failed sampling system resources for bulk autoscaling")
		return false
	}
	return cpuValues[0] >= w.cpuLimitPercent || memoryStats.UsedPercent >= w.memoryLimitPercent
}

func (w *AsyncBulkWriter) recordError(err error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.firstErr == nil {
		w.firstErr = err
	}
}

func (w *AsyncBulkWriter) raiseIfFailed() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.firstErr == nil {
		return nil
	}
	return fmt.Errorf("Async bulk writer failed: %w", w.firstErr)
}

func cloneActionSlice(actions []map[string]any) []map[string]any {
	out := make([]map[string]any, 0, len(actions))
	for _, action := range actions {
		out = append(out, cloneMap(action))
	}
	return out
}

func durationFromSeconds(seconds float64, fallback time.Duration) time.Duration {
	if seconds <= 0 {
		return fallback
	}
	return time.Duration(seconds * float64(time.Second))
}

func clampFloat(value float64, minimum float64, maximum float64) float64 {
	if value < minimum {
		return minimum
	}
	if value > maximum {
		return maximum
	}
	return value
}
