package worker

import "testing"

func TestResolveDefaultsToSingleWorker(t *testing.T) {
	runtime, err := Resolve()
	if err != nil {
		t.Fatalf("Resolve returned error: %v", err)
	}
	if runtime.Count != 1 || runtime.Index != 0 {
		t.Fatalf("expected single-worker runtime, got %#v", runtime)
	}
}

func TestResolveReadsWorkerRuntimeFromEnv(t *testing.T) {
	t.Setenv("RCA_WORKER_COUNT", "4")
	t.Setenv("RCA_WORKER_ID", "2")

	runtime, err := Resolve()
	if err != nil {
		t.Fatalf("Resolve returned error: %v", err)
	}
	if runtime.Count != 4 || runtime.Index != 2 {
		t.Fatalf("unexpected runtime: %#v", runtime)
	}
}

func TestResolveRejectsOutOfRangeWorkerIndex(t *testing.T) {
	t.Setenv("RCA_WORKER_COUNT", "2")
	t.Setenv("RCA_WORKER_ID", "2")

	if _, err := Resolve(); err == nil {
		t.Fatal("expected invalid worker index to fail")
	}
}

func TestScopedPathAddsWorkerSuffixOnlyForParallelWorkers(t *testing.T) {
	single := Runtime{Count: 1, Index: 0}
	if got := single.ScopedPath(`data\results\rca_results.json`); got != `data\results\rca_results.json` {
		t.Fatalf("expected single-worker path to remain unchanged, got %q", got)
	}

	parallel := Runtime{Count: 3, Index: 1}
	if got := parallel.ScopedPath(`data\results\rca_results.json`); got != `data\results\rca_results.worker-1.json` {
		t.Fatalf("unexpected scoped path: %q", got)
	}
}
