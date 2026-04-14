# Log RCA Engine

`log_rca_engine` is the score-first RCA consumer for the repo.

It reads correlation events from Elasticsearch, computes a 0-10 confidence score from sequence quality, topology/dependency coherence, timing, severity, and rule completeness, then:

- stores `confirmed_rca` incidents when the score is at or above the configured threshold
- stores `probable_cause` incidents when the score stays below the threshold
- optionally calls OpenAI for a structured RCA explanation only for the high-confidence incidents

## Current flow

```text
signalizing -> correlation-engine -> rca_correlated_events -> log-rca-engine -> JSON result store
```

## Inputs

- Correlation events: `elasticsearch.correlation_index`
- Correlation rules: `rules.file`
- Static topology: `topology.file`

Topology matching is IP-aware. When a topology node provides `device_ip`, the scorer uses `host.ip` from the original Elasticsearch log evidence as the primary identity and falls back to `service.name`, `event.module`, or `host.name` only when no usable IP is available.

If `host.ip` contains multiple interface addresses in one field, the engine extracts all IPv4 values and uses the topology-matching device IP candidate when one of them matches your topology.

For service-aware deployments where multiple services run on the same device IP, the scorer supports service-on-IP node identities such as `10.0.4.72::api`. It will use `service_relations` and composite `dependencies` entries to score upstream and dependency paths between services on the same host.

## Confidence Score

The confidence score is the main numerical decision layer of `log_rca_engine`.
It answers one question:

```text
How strong is the evidence that this incident already points to a real RCA?
```

The engine first builds a normalized score in the range `0.0` to `1.0`, then converts it to a `0` to `10` confidence score.

## Mathematical Symbols

We use the following symbols in the formulas below:

```text
S_seq   = sequence_match_score
S_dep   = dependency_match_score
S_time  = time_proximity_score
S_sev   = signal_severity_score
S_rule  = rule_completeness_score

C_topo  = topology_coverage
C_id    = identity_confidence
P_contra = contradiction_penalty

w_seq   = 0.30
w_dep   = 0.25
w_time  = 0.15
w_sev   = 0.15
w_rule  = 0.15
```

Helper:

```text
clamp01(x) = max(0, min(1, x))
```

## Master Formula

The final score is calculated in two stages.

Stage 1: weighted normalized score

```text
Score_base =
  w_seq  * S_seq  +
  w_dep  * S_dep  +
  w_time * S_time +
  w_sev  * S_sev  +
  w_rule * S_rule
```

Since the default weights add up to `1.00`, this is already normalized.

Stage 2: contradiction adjustment and conversion to a 10-point scale

```text
Confidence_score = 10 * Score_base * P_contra
```

Classification rule:

```text
if Confidence_score >= 7.0 and all confirmation gates pass
    classification = confirmed_rca
else
    classification = probable_cause
```

## 1. Sequence Match Score

This comes directly from the correlation engine, but it is not an arbitrary number.
The correlation engine calculates it from rule-step progress, then RCA consumes that value.

### 1.1 Raw sequence-match formula inside correlation engine

Suppose a rule has `N` ordered steps.

For each step `i`:

```text
required_i = min_count_i
observed_i = how many logs matched that step
matched_i  = min(observed_i, required_i)
```

The correlation engine then calculates:

```text
completed_prefix_steps = number of consecutive steps, from the start, that are fully matched
```

and:

```text
partial_next_step_progress =
  matched_first_incomplete_step / required_first_incomplete_step
```

Only the first incomplete step contributes partial progress.
Later steps do not increase `sequence_match` if the earlier prefix is not complete.

Raw formula:

```text
sequence_match_raw =
  (completed_prefix_steps + partial_next_step_progress) / N
```

Then RCA uses:

Formula:

```text
S_seq = clamp01(sequence_match_raw)
```

Example:

```text
sequence_match_raw = 0.80
S_seq = clamp01(0.80) = 0.80
```

More examples:

```text
Example A:
sequence_match_raw = 0.25
S_seq = clamp01(0.25) = 0.25
```

```text
Example B:
sequence_match_raw = 1.20
S_seq = clamp01(1.20) = 1.00
```

```text
Example C:
sequence_match_raw = -0.10
S_seq = clamp01(-0.10) = 0.00
```

### 1.2 Sequence-match worked sums from correlation engine

Example D: two full prefix steps completed

Rule:

```text
step 1 requires 3 logs
step 2 requires 1 log
step 3 requires 1 log
N = 3
```

Observed:

```text
step 1 observed = 3 -> matched_1 = min(3, 3) = 3
step 2 observed = 1 -> matched_2 = min(1, 1) = 1
step 3 observed = 0 -> matched_3 = min(0, 1) = 0
```

Then:

```text
completed_prefix_steps = 2
partial_next_step_progress = 0 / 1 = 0
sequence_match_raw = (2 + 0) / 3 = 0.6667
S_seq = 0.6667
```

Example E: first step is only partially matched

Rule:

```text
step 1 requires 3 logs
step 2 requires 1 log
step 3 requires 1 log
N = 3
```

Observed:

```text
step 1 observed = 2 -> matched_1 = min(2, 3) = 2
step 2 observed = 0 -> matched_2 = min(0, 1) = 0
step 3 observed = 0 -> matched_3 = min(0, 1) = 0
```

Then:

```text
completed_prefix_steps = 0
partial_next_step_progress = 2 / 3 = 0.6667
sequence_match_raw = (0 + 0.6667) / 3 = 0.2222
S_seq = 0.2222
```

Example F: later steps matched, but prefix is broken

Rule:

```text
step 1 requires 3 logs
step 2 requires 1 log
step 3 requires 1 log
N = 3
```

Observed:

```text
step 1 observed = 2 -> matched_1 = 2
step 2 observed = 1 -> matched_2 = 1
step 3 observed = 1 -> matched_3 = 1
```

For `sequence_match`, the first incomplete step is still step 1, so later steps do not add prefix progress:

```text
completed_prefix_steps = 0
partial_next_step_progress = 2 / 3 = 0.6667
sequence_match_raw = (0 + 0.6667) / 3 = 0.2222
S_seq = 0.2222
```

## 2. Topology Coverage and Identity Confidence

These are not separate weighted parameters, but they directly modify the dependency and rule-completeness parts.

### 2.1 Topology Coverage

```text
C_topo = known_unique_matched_identities / total_unique_matched_identities
```

Example:

```text
matched identities = [10.0.4.72::nginx, 10.0.4.72::api, 10.0.8.99::unknown]
known identities   = [10.0.4.72::nginx, 10.0.4.72::api]

C_topo = 2 / 3 = 0.6667
```

More examples:

```text
Example A:
matched identities = [10.0.4.72::api, 10.0.4.72::mongodb]
known identities   = [10.0.4.72::api, 10.0.4.72::mongodb]

C_topo = 2 / 2 = 1.00
```

```text
Example B:
matched identities = [10.0.9.20::cache]
known identities   = []

C_topo = 0 / 1 = 0.00
```

### 2.2 Identity Confidence

Each matched log is first resolved to a topology identity.

The resolver uses these confidence values:

```text
host.ip::service.name  -> 1.00
host.ip only           -> 0.85
service.name only      -> 0.65
host.name only         -> 0.40
```

Then:

```text
C_id = average(identity_confidence_i)
```

Example:

```text
resolved identities:
  10.0.4.72::api      -> 1.00
  10.0.4.72::mongodb  -> 1.00
  10.0.4.72           -> 0.85

C_id = (1.00 + 1.00 + 0.85) / 3 = 0.95
```

More examples:

```text
Example A:
resolved identities:
  10.0.4.72::api -> 1.00
  10.0.4.72      -> 0.85
  api            -> 0.65
  host-a         -> 0.40

C_id = (1.00 + 0.85 + 0.65 + 0.40) / 4
C_id = 2.90 / 4 = 0.725
```

```text
Example B:
resolved identities:
  host-a -> 0.40
  host-b -> 0.40

C_id = (0.40 + 0.40) / 2 = 0.40
```

## 3. Dependency Match Score

This measures whether the matched services are actually connected in topology, and how strong that connection is.

The scorer first builds an ordered list of topology identities and removes consecutive duplicates:

```text
I = compress_consecutive_duplicates(ordered_topology_identities)
```

If only one identity remains, then:

```text
S_dep = clamp01(C_topo * C_id)
```

If two or more identities remain, the engine scores each adjacent pair.

### 3.1 Directed edge strength

The topology graph is directional and weighted.

Typical directional factors:

```text
upstream / calls:
  forward = 1.00
  reverse = 0.85

depends_on / uses / requires / receives_from:
  forward = 0.85
  reverse = 1.00

peer / replica / sibling:
  forward = 0.85
  reverse = 0.85
```

### 3.2 Path score

For one candidate path with `h` hops:

```text
Path_strength_avg = (edge_strength_1 + edge_strength_2 + ... + edge_strength_h) / h
```

Hop factor:

```text
Hop_factor(1) = 1.00
Hop_factor(2) = 0.75
Hop_factor(3) = 0.50
Hop_factor(4) = 0.35
```

Path score:

```text
Path_score = clamp01(Path_strength_avg * Hop_factor(h))
```

For each adjacent identity pair `(I_k, I_k+1)`, the engine checks all directed paths up to 4 hops and keeps the best one:

```text
Pair_score_k = max(Path_score over all directed paths from I_k to I_k+1, up to 4 hops)
```

Average pair score:

```text
Pair_avg = (Pair_score_1 + Pair_score_2 + ... + Pair_score_n) / n
```

Final dependency score:

```text
S_dep = clamp01(Pair_avg * C_topo * C_id)
```

### 3.3 Dependency worked sum

Assume:

```text
I = [10.0.4.72::nginx, 10.0.4.72::api, 10.0.4.72::mongodb]
C_topo = 1.00
C_id   = 1.00
```

Suppose:

```text
nginx -> api       has path score 1.00
api -> mongodb     has path score 0.85
```

Then:

```text
Pair_avg = (1.00 + 0.85) / 2 = 0.925
S_dep = clamp01(0.925 * 1.00 * 1.00) = 0.925
```

More dependency examples:

```text
Example A: single identity only

I = [10.0.4.72::mongodb]
C_topo = 1.00
C_id   = 0.85

S_dep = clamp01(1.00 * 0.85) = 0.85
```

```text
Example B: one good pair and one broken pair

I = [10.0.4.72::nginx, 10.0.4.72::api, 10.0.9.20::redis]
C_topo = 0.6667
C_id   = 1.00

Pair_score_1 = 1.00
Pair_score_2 = 0.00

Pair_avg = (1.00 + 0.00) / 2 = 0.50
S_dep = clamp01(0.50 * 0.6667 * 1.00) = 0.3334
```

```text
Example C: two-hop path with weighted direction

Suppose:
service-a -> service-b has edge strength 0.85
service-b -> service-c has edge strength 1.00

h = 2
Path_strength_avg = (0.85 + 1.00) / 2 = 0.925
Hop_factor(2) = 0.75
Path_score = 0.925 * 0.75 = 0.69375

If C_topo = 1.00 and C_id = 1.00:
S_dep = 0.6938
```

## 4. Time Proximity Score

This measures whether the matched logs happened close enough in time to support one incident chain.

### 4.0 Where the time values come from

The time-proximity calculation uses two different data sources.

From matched logs:

```text
step times such as [10:00, 10:02, 10:03]
```

These come from the matched evidence log timestamps:

```text
event.log_id[].timestamp
```

From correlation-rule audit metadata:

```text
step within
max_gap_between_steps
rule window
```

These do not come from the raw logs themselves.
They are copied by the correlation engine from the rule definition into the correlation-event audit.

So the source split is:

```text
timestamps               -> from matched logs
step within              -> from rule sequence[].within
max_gap_between_steps    -> from rule max_gap_between_steps
rule window              -> from rule window
```

That means this example:

```text
step 1 times = [10:00, 10:02]
step 1 within = 5m
step 2 times = [10:03]
max_gap_between_steps = 3m
```

should be read as:

```text
[10:00, 10:02, 10:03] -> fetched from log timestamps
5m and 3m             -> fetched from rule/audit metadata
```

The core time helper is:

```text
closeness(actual, limit) =
  1.00, if actual <= 0
  0.00, if actual >= limit
  clamp01(1 - actual / limit), otherwise
```

### 4.1 Step score

For one audit step:

```text
step_span_i = max(step_times_i) - min(step_times_i)
```

If a step has no matched timestamps:

```text
step_score_i = 0.00
```

If a step has only one timestamp, or the `within` duration is missing/invalid:

```text
step_score_i = 0.50
```

Otherwise:

```text
step_score_i = closeness(step_span_i, step_within_i)
```

### 4.2 Gap score between steps

For adjacent steps `i` and `i+1`:

```text
gap_i = max(0, first_timestamp_of_step_(i+1) - last_timestamp_of_step_i)
```

If a valid gap limit exists:

```text
gap_score_i = closeness(gap_i, gap_limit_i)
```

If the gap limit is missing:

```text
gap_score_i = 0.50
```

### 4.3 Final time score

If at least one step/gap component exists:

```text
S_time = clamp01((sum of all step_score_i and gap_score_i) / number_of_components)
```

If there are no audit timing components:

```text
overall_span = latest_log_time - earliest_log_time
```

Then:

```text
if only one usable timestamp exists:
    S_time = 0.35
else if rule window exists:
    S_time = closeness(overall_span, rule_window)
else
    S_time = 0.35
```

### 4.4 Time worked sum

Assume:

```text
step 1 times = [10:00, 10:02]
step 1 within = 5m
step 2 times = [10:03]
max_gap_between_steps = 3m
```

Step 1:

```text
step_span_1 = 2m
step_score_1 = closeness(2m, 5m) = 1 - 2/5 = 0.60
```

Step 2:

```text
step_score_2 = 0.50
```

because that step has only one matched timestamp.

Gap:

```text
gap_1 = 10:03 - 10:02 = 1m
gap_score_1 = closeness(1m, 3m) = 1 - 1/3 = 0.6667
```

Final:

```text
S_time = (0.60 + 0.50 + 0.6667) / 3 = 0.5889
```

More time examples:

```text
Example A: perfect overlap / immediate continuation

step 1 times = [10:00, 10:01]
step 1 within = 5m
step 2 times = [10:01]
max_gap_between_steps = 3m

step_score_1 = closeness(1m, 5m) = 1 - 1/5 = 0.80
step_score_2 = 0.50
gap_1 = max(0, 10:01 - 10:01) = 0
gap_score_1 = closeness(0, 3m) = 1.00

S_time = (0.80 + 0.50 + 1.00) / 3 = 0.7667
```

```text
Example B: fallback with one timestamp only

usable timestamps = 1

S_time = 0.35
```

```text
Example C: fallback using rule window

earliest log = 10:00
latest log   = 10:06
rule window  = 15m

overall_span = 6m
S_time = closeness(6m, 15m) = 1 - 6/15 = 0.60
```

```text
Example D: no rule window and no audit timing

usable timestamps > 1
rule window missing

S_time = 0.35
```

## 5. Signal Severity Score

Each matched evidence log is mapped to a severity weight:

```text
critical, crit, fatal, panic, alert, emergency, emerg -> 1.00
error, err, failure, failed                           -> 0.85
warning, warn                                         -> 0.60
info, notice, informational                           -> 0.35
anything else                                         -> 0.20
```

Then:

```text
Severity_max = max(severity_weight_i)
Severity_avg = (sum of severity_weight_i) / number_of_logs
```

Final severity score:

```text
S_sev = clamp01(0.6 * Severity_max + 0.4 * Severity_avg)
```

### Signal severity worked sum

Assume three matched logs:

```text
critical = 1.00
warning  = 0.60
info     = 0.35
```

Then:

```text
Severity_max = 1.00
Severity_avg = (1.00 + 0.60 + 0.35) / 3 = 0.65
S_sev = 0.6 * 1.00 + 0.4 * 0.65
S_sev = 0.60 + 0.26 = 0.86
```

More severity examples:

```text
Example A: one error only

Severity_max = 0.85
Severity_avg = 0.85
S_sev = 0.6 * 0.85 + 0.4 * 0.85 = 0.85
```

```text
Example B: only warnings

weights = [0.60, 0.60, 0.60]
Severity_max = 0.60
Severity_avg = (0.60 + 0.60 + 0.60) / 3 = 0.60
S_sev = 0.6 * 0.60 + 0.4 * 0.60 = 0.60
```

```text
Example C: unknown severities

weights = [0.20, 0.20]
Severity_max = 0.20
Severity_avg = (0.20 + 0.20) / 2 = 0.20
S_sev = 0.6 * 0.20 + 0.4 * 0.20 = 0.20
```

```text
Example D: no matched evidence logs

S_sev = 0.00
```

## 6. Rule Completeness Score

This starts with the raw correlation-engine field `rule_completion`, then reduces it if topology coverage or identity quality is weak.

### 6.1 Raw rule-completeness formula inside correlation engine

Suppose a rule has `N` steps.

For each step `i`:

```text
required_i = min_count_i
observed_i = how many logs matched that step
matched_i  = min(observed_i, required_i)
```

The correlation engine calculates:

```text
total_required   = required_1 + required_2 + ... + required_N
matched_required = matched_1 + matched_2 + ... + matched_N
```

Then:

```text
rule_completion_raw = matched_required / total_required
```

This is different from `sequence_match`.

- `rule_completion_raw` counts total evidence matched across all steps
- `sequence_match_raw` measures ordered prefix progress through the rule

Then RCA adjusts the raw value with topology and identity quality.

Formula:

```text
S_rule = clamp01(rule_completion_raw) * C_topo * C_id
```

### Rule completeness worked sum

Assume:

```text
rule_completion_raw = 0.80
C_topo = 0.75
C_id   = 0.95
```

Then:

```text
S_rule = 0.80 * 0.75 * 0.95 = 0.57
```

So even though raw rule completion is `0.80`, the usable RCA strength drops to `0.57` because topology and identity support are not perfect.

### 6.2 Rule-completeness worked sums from correlation engine

Example A: partial evidence across the whole rule

Rule:

```text
step 1 requires 3 logs
step 2 requires 1 log
step 3 requires 1 log
```

Then:

```text
total_required = 3 + 1 + 1 = 5
```

Observed:

```text
step 1 observed = 2 -> matched_1 = min(2, 3) = 2
step 2 observed = 0 -> matched_2 = min(0, 1) = 0
step 3 observed = 0 -> matched_3 = min(0, 1) = 0
```

So:

```text
matched_required = 2 + 0 + 0 = 2
rule_completion_raw = 2 / 5 = 0.40
```

If `C_topo = 1.00` and `C_id = 1.00`, then:

```text
S_rule = 0.40 * 1.00 * 1.00 = 0.40
```

Example B: almost complete rule

Observed:

```text
step 1 observed = 3 -> matched_1 = 3
step 2 observed = 1 -> matched_2 = 1
step 3 observed = 0 -> matched_3 = 0
```

So:

```text
matched_required = 3 + 1 + 0 = 4
rule_completion_raw = 4 / 5 = 0.80
```

If `C_topo = 0.75` and `C_id = 0.95`, then:

```text
S_rule = 0.80 * 0.75 * 0.95 = 0.57
```

Example C: later evidence exists even if sequence is weak

Observed:

```text
step 1 observed = 2 -> matched_1 = 2
step 2 observed = 1 -> matched_2 = 1
step 3 observed = 1 -> matched_3 = 1
```

Then:

```text
matched_required = 2 + 1 + 1 = 4
rule_completion_raw = 4 / 5 = 0.80
```

But from the sequence section, the same case has:

```text
sequence_match_raw = 0.2222
```

This example shows why the engine keeps both numbers:

```text
rule_completion_raw -> how much total evidence exists
sequence_match_raw  -> how well the evidence follows the expected order
```

More rule-completeness examples:

```text
Example A: very strong evidence

rule_completion = 1.00
C_topo = 1.00
C_id   = 1.00

S_rule = 1.00 * 1.00 * 1.00 = 1.00
```

```text
Example B: partial rule with weak topology support

rule_completion = 0.60
C_topo = 0.50
C_id   = 0.65

S_rule = 0.60 * 0.50 * 0.65
S_rule = 0.195
```

## 7. Contradiction Penalty

This is a multiplier that reduces the final score when nearby logs contradict the current RCA story.

If there are no nearby logs:

```text
P_contra = 1.00
```

Otherwise, the engine computes a raw penalty and then converts it into a multiplier.

### 7.1 Nearby log relevance

Each nearby log gets a relevance factor:

```text
same service -> 1.00
same host    -> 0.90
same IP      -> 1.00
other nearby -> 0.60
```

### 7.2 Penalty constants

```text
explicit contradiction penalty = 0.35
recovery contradiction penalty = 0.20
competing signal penalty       = 0.10
maximum total penalty          = 0.75
```

### 7.3 Raw contradiction formula

```text
Penalty_raw =
  sum(0.35 * relevance_j for explicit contradiction logs) +
  sum(0.20 * relevance_k for recovery logs) +
  sum(0.10 * relevance_m for competing high-severity logs)
```

Then:

```text
Penalty_capped = min(Penalty_raw, 0.75)
P_contra = clamp01(1 - Penalty_capped)
```

### Contradiction worked sum

Assume nearby evidence contains:

```text
1 recovery log on the same host
1 competing high-severity log on a weakly related service
```

Then:

```text
Penalty_raw = (0.20 * 0.90) + (0.10 * 0.60)
Penalty_raw = 0.18 + 0.06 = 0.24

P_contra = 1 - 0.24 = 0.76
```

So the final score keeps only `76%` of the base score.

More contradiction examples:

```text
Example A: no contradiction at all

Penalty_raw = 0.00
P_contra = 1 - 0.00 = 1.00
```

```text
Example B: one explicit contradiction on same IP

Penalty_raw = 0.35 * 1.00 = 0.35
P_contra = 1 - 0.35 = 0.65
```

```text
Example C: capped penalty

Penalty_raw =
  (0.35 * 1.00) +
  (0.35 * 1.00) +
  (0.20 * 1.00)

Penalty_raw = 0.90
Penalty_capped = min(0.90, 0.75) = 0.75
P_contra = 1 - 0.75 = 0.25
```

## 8. Completed Step Coverage

This is not directly weighted in the final score, but it is used by the confirmation gates.

If the audit contains `N` rule steps and `M` of them have reached their required match count, then:

```text
Completed_step_coverage = M / N
```

Where a step is considered complete if:

```text
matched_count >= required_count
```

Example A:

```text
rule steps = 3
completed steps = 2

Completed_step_coverage = 2 / 3 = 0.6667
```

Example B:

```text
rule steps = 4
completed steps = 1

Completed_step_coverage = 1 / 4 = 0.25
```

For confirmation:

```text
single-step rule  -> at least 1 completed step
multi-step rule   -> at least 2 completed steps
```

## 9. Full Solved Example

Assume one incident has:

```text
S_seq   = 0.80
S_dep   = 0.925
S_time  = 0.5889
S_sev   = 0.86
S_rule  = 0.57
P_contra = 0.76
```

Step 1: weighted base score

```text
Score_base =
  0.30 * 0.80   +
  0.25 * 0.925  +
  0.15 * 0.5889 +
  0.15 * 0.86   +
  0.15 * 0.57
```

```text
Score_base =
  0.2400 +
  0.2313 +
  0.0883 +
  0.1290 +
  0.0855
```

```text
Score_base = 0.7741
```

Step 2: contradiction adjustment and conversion to 10-point scale

```text
Confidence_score = 10 * 0.7741 * 0.76
Confidence_score = 5.8832
```

Final result:

```text
Confidence_score = 5.8832
classification = probable_cause
```

If the contradiction penalty had been `1.00`, then:

```text
Confidence_score = 10 * 0.7741 * 1.00 = 7.741
```

That incident could become `confirmed_rca` only if the confirmation gates also pass.

## 10. Confirmation Gates

The numeric score alone is not enough. The engine also checks minimum safety gates.

Current confirmation gates:

```text
S_seq      >= 0.55
S_rule     >= 0.45
C_topo     >= 0.50
C_id       >= 0.60
S_time     >= 0.30
P_contra   >= 0.80
```

And if audit steps exist:

```text
single-step rule  -> at least 1 completed step
multi-step rule   -> at least 2 completed steps
```

So this can happen:

```text
Confidence_score >= 7.0
but classification = probable_cause
```

if one of the safety gates fails.

### Gate example 1: score is high but still not confirmed

Assume:

```text
Confidence_score = 7.80
S_seq  = 0.82
S_rule = 0.71
C_topo = 0.88
C_id   = 0.92
S_time = 0.22
P_contra = 0.95
```

Even though the numeric score is above `7.0`, confirmation fails because:

```text
S_time = 0.22 < 0.30
```

Result:

```text
classification = probable_cause
```

### Gate example 2: numeric score and gates both pass

Assume:

```text
Confidence_score = 8.10
S_seq  = 0.84
S_rule = 0.68
C_topo = 0.90
C_id   = 0.95
S_time = 0.63
P_contra = 0.92
completed multi-step rule steps = 3
```

All gates pass, so:

```text
classification = confirmed_rca
```

## 11. Parameter Contribution to the Final Score

You can also look at the score as a sum of five weighted contributions.

If:

```text
Contribution_seq  = 0.30 * S_seq
Contribution_dep  = 0.25 * S_dep
Contribution_time = 0.15 * S_time
Contribution_sev  = 0.15 * S_sev
Contribution_rule = 0.15 * S_rule
```

Then:

```text
Score_base =
  Contribution_seq +
  Contribution_dep +
  Contribution_time +
  Contribution_sev +
  Contribution_rule
```

Example:

```text
S_seq  = 0.80  -> Contribution_seq  = 0.30 * 0.80  = 0.2400
S_dep  = 0.60  -> Contribution_dep  = 0.25 * 0.60  = 0.1500
S_time = 0.50  -> Contribution_time = 0.15 * 0.50  = 0.0750
S_sev  = 0.90  -> Contribution_sev  = 0.15 * 0.90  = 0.1350
S_rule = 0.70  -> Contribution_rule = 0.15 * 0.70  = 0.1050
```

So:

```text
Score_base = 0.2400 + 0.1500 + 0.0750 + 0.1350 + 0.1050 = 0.7050
```

If `P_contra = 0.90`, then:

```text
Confidence_score = 10 * 0.7050 * 0.90 = 6.345
```

## Why This Helps Accuracy

The scorer does not rely on only one signal. It combines:

- sequence quality from the correlation engine
- real upstream and dependency relationships from topology
- timing closeness between matched logs
- severity strength of the evidence
- completeness of the matched rule

This makes the RCA process more reliable than using only correlation count or only rule matching. High-confidence incidents go to the LLM for explanation. Lower-confidence incidents are still stored as `probable_cause` so they are not lost.

## Replay Safety

To avoid missing late-arriving correlation documents, the reader replays a recent time window on every cycle and relies on `incident_id + result_signature` dedupe before rescoring.

- Replay window config: `elasticsearch.replay_window`
- Default replay window: `1h`
- Checkpoint behavior: the saved checkpoint keeps the cycle watermark, while pagination `search_after` is used only inside a single run

## Outputs

- Result file: `storage.results_file`
- Checkpoint file: `storage.checkpoint_file`

The result file keeps one record per `incident_id` in a top-level `items` array.

## Run

```powershell
cd "D:\Code for tutorials\rca\log_rca_engine"
.\rebuild.ps1
.\bin\log-rca-engine.exe --config .\config\config.yml --run-once
```

PM2:

```powershell
pm2 start .\app.json
```

## OpenAI

OpenAI is disabled by default. To enable it, set these in `config/config.yml`:

- `openai.enabled: true`
- `openai.api_key`
- `openai.model` which now defaults to `gpt-4o-mini`

The client uses the OpenAI Responses API with a dedicated conversation handler, a structured prompt builder, and a strict JSON schema so the stored RCA summary stays machine-readable.
