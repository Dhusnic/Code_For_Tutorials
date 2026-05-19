package redis

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"sort"
	"strconv"
	"strings"
	"time"

	"log_correlation_engine/internal/config"
	"log_correlation_engine/internal/models"

	goredis "github.com/redis/go-redis/v9"
)

type Store struct {
	client                goredis.UniversalClient
	keyPrefix             string
	hashField             string
	incidentField         string
	legacyOrgIndexKey     string
	activeOrgSetKey       string
	activeOrgRebuildKey   string
	activeOrgCursorKey    string
	resultList            string
	resultListMaxLen      int
	signalStreamEnabled   bool
	signalStreamKey       string
	signalStreamBatchSize int
	logger                *slog.Logger
}

const activeIncidentHashField = "active_incidents"

const (
	activeOrgRebuildLockTTL               = 90 * time.Second
	activeOrgRebuildPollWait              = 200 * time.Millisecond
	activeOrgRebuildScanCount       int64 = 250
	activeOrgRebuildMaxBatches            = 8
	activeOrgRebuildDeadlineReserve       = 3 * time.Second
)

func NewStore(client goredis.UniversalClient, cfg config.RedisConfig, logger *slog.Logger) *Store {
	keyPrefix := strings.TrimSuffix(cfg.KeyPrefix, ":")
	return &Store{
		client:                client,
		keyPrefix:             keyPrefix,
		hashField:             cfg.HashField,
		incidentField:         activeIncidentHashField,
		legacyOrgIndexKey:     fmt.Sprintf("%s:organizations", keyPrefix),
		activeOrgSetKey:       fmt.Sprintf("%s:active_organizations", keyPrefix),
		activeOrgRebuildKey:   fmt.Sprintf("%s:active_organizations:rebuild_lock", keyPrefix),
		activeOrgCursorKey:    fmt.Sprintf("%s:active_organizations:rebuild_cursor", keyPrefix),
		resultList:            cfg.ResultList,
		resultListMaxLen:      cfg.ResultListMaxLen,
		signalStreamEnabled:   cfg.SignalStreamEnabled,
		signalStreamKey:       cfg.SignalStreamKey,
		signalStreamBatchSize: cfg.SignalStreamBatchSize,
		logger:                logger,
	}
}

func (s *Store) OrganizationKey(organization string) string {
	return fmt.Sprintf("%s:%s", s.keyPrefix, organization)
}

func (s *Store) ResultKey(organization string) string {
	return fmt.Sprintf("%s:%s:%s", s.keyPrefix, organization, s.resultList)
}

func (s *Store) IncidentKey(organization, incidentID string) string {
	return fmt.Sprintf("%s:%s:incident:%s", s.keyPrefix, organization, incidentID)
}

func (s *Store) IncidentIndexKey(organization string) string {
	return fmt.Sprintf("%s:%s:active_incidents", s.keyPrefix, organization)
}

func (s *Store) ActiveIncidentStateKey(organization string) string {
	return fmt.Sprintf("%s:%s:active_incident_states", s.keyPrefix, organization)
}

func (s *Store) SignalStreamKey() string {
	return s.signalStreamKey
}

func (s *Store) ListOrganizations(ctx context.Context) ([]string, error) {
	organizations, rebuildPending, err := s.activeOrganizationsState(ctx)
	if err != nil {
		return nil, err
	}
	if len(organizations) > 0 && !rebuildPending {
		return organizations, nil
	}

	return s.rebuildActiveOrganizations(ctx, organizations, rebuildPending)
}

func (s *Store) rebuildActiveOrganizations(ctx context.Context, current []string, rebuildPending bool) ([]string, error) {
	lockToken, acquired, err := s.tryClaimActiveOrganizationRebuildLock(ctx)
	if err != nil {
		return nil, err
	}
	if !acquired {
		if len(current) > 0 {
			return current, nil
		}
		return s.waitForActiveOrganizations(ctx)
	}
	defer s.releaseActiveOrganizationRebuildLock(context.Background(), lockToken)

	organizations, pending, err := s.advanceActiveOrganizationRebuild(ctx, rebuildPending)
	if err != nil {
		return nil, err
	}
	if len(organizations) > 0 {
		return organizations, nil
	}
	if len(current) > 0 {
		return current, nil
	}
	if pending {
		if s.logger != nil {
			s.logger.Debug(
				"active organization rebuild still in progress",
				"key", s.activeOrgSetKey,
				"cursor_key", s.activeOrgCursorKey,
			)
		}
	}
	return nil, nil
}

func (s *Store) waitForActiveOrganizations(ctx context.Context) ([]string, error) {
	ticker := time.NewTicker(activeOrgRebuildPollWait)
	defer ticker.Stop()

	for {
		organizations, err := s.activeOrganizations(ctx)
		if err != nil {
			return nil, err
		}
		if len(organizations) > 0 {
			return organizations, nil
		}

		lockExists, err := s.client.Exists(ctx, s.activeOrgRebuildKey).Result()
		if err != nil && !errors.Is(err, goredis.Nil) {
			return nil, fmt.Errorf("inspect active organization rebuild lock %s: %w", s.activeOrgRebuildKey, err)
		}
		if lockExists == 0 {
			if s.logger != nil {
				s.logger.Debug(
					"active organization rebuild completed without populating index",
					"key", s.activeOrgSetKey,
				)
			}
			return nil, nil
		}

		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-ticker.C:
		}
	}
}

func (s *Store) activeOrganizationsState(ctx context.Context) ([]string, bool, error) {
	organizations, err := s.activeOrganizations(ctx)
	if err != nil {
		return nil, false, err
	}
	if strings.TrimSpace(s.activeOrgCursorKey) == "" {
		return organizations, false, nil
	}
	cursorExists, err := s.client.Exists(ctx, s.activeOrgCursorKey).Result()
	if err != nil && !errors.Is(err, goredis.Nil) {
		return nil, false, fmt.Errorf("inspect active organization rebuild cursor %s: %w", s.activeOrgCursorKey, err)
	}
	return organizations, cursorExists > 0, nil
}

func (s *Store) tryClaimActiveOrganizationRebuildLock(ctx context.Context) (string, bool, error) {
	if strings.TrimSpace(s.activeOrgRebuildKey) == "" {
		return "", true, nil
	}

	token, err := randomToken()
	if err != nil {
		return "", false, fmt.Errorf("create active organization rebuild lock token: %w", err)
	}

	acquired, err := s.client.SetNX(ctx, s.activeOrgRebuildKey, token, activeOrgRebuildLockTTL).Result()
	if err != nil {
		return "", false, fmt.Errorf("claim active organization rebuild lock %s: %w", s.activeOrgRebuildKey, err)
	}
	return token, acquired, nil
}

func (s *Store) releaseActiveOrganizationRebuildLock(ctx context.Context, token string) {
	if strings.TrimSpace(s.activeOrgRebuildKey) == "" || strings.TrimSpace(token) == "" {
		return
	}

	const releaseScript = `
if redis.call("GET", KEYS[1]) == ARGV[1] then
	return redis.call("DEL", KEYS[1])
end
return 0
`
	if err := s.client.Eval(ctx, releaseScript, []string{s.activeOrgRebuildKey}, token).Err(); err != nil &&
		!errors.Is(err, goredis.Nil) &&
		s.logger != nil {
		s.logger.Warn(
			"failed to release active organization rebuild lock",
			"key", s.activeOrgRebuildKey,
			"error", err,
		)
	}
}

func (s *Store) advanceActiveOrganizationRebuild(ctx context.Context, rebuildPending bool) ([]string, bool, error) {
	cursor, hadCursor, err := s.activeOrganizationRebuildCursor(ctx)
	if err != nil {
		return nil, rebuildPending, err
	}
	if !hadCursor {
		s.cleanupLegacyOrganizationIndex(ctx)
	}

	pattern := s.keyPrefix + ":*"
	seen := make(map[string]struct{})
	scanCursor := cursor
	remainingBatches := activeOrgRebuildMaxBatches
	complete := false

	for remainingBatches > 0 {
		if s.shouldYieldActiveOrganizationRebuild(ctx) {
			break
		}

		keys, nextCursor, err := s.client.Scan(ctx, scanCursor, pattern, activeOrgRebuildScanCount).Result()
		if err != nil {
			return nil, rebuildPending, fmt.Errorf("scan redis keys: %w", err)
		}

		for _, key := range keys {
			if key == s.signalStreamKey || key == s.activeOrgSetKey {
				continue
			}
			organization, needsInspection := s.scanOrganizationFromKey(key)
			if organization == "" {
				continue
			}
			if needsInspection {
				signalsExist, incidentsExist, err := s.organizationHashFieldsExist(ctx, key)
				if err != nil {
					return nil, rebuildPending, fmt.Errorf("inspect redis hash for %s: %w", key, err)
				}
				if !signalsExist && !incidentsExist {
					continue
				}
			}
			if _, ok := seen[organization]; ok {
				continue
			}
			seen[organization] = struct{}{}
		}

		scanCursor = nextCursor
		remainingBatches--
		complete = scanCursor == 0
		if complete {
			break
		}
	}

	discovered := sortedKeys(seen)
	if len(discovered) > 0 {
		if err := s.client.SAdd(ctx, s.activeOrgSetKey, stringSliceToAny(discovered)...).Err(); err != nil && s.logger != nil {
			s.logger.Warn("failed to rebuild active organization index", "key", s.activeOrgSetKey, "error", err)
		}
	}

	if complete {
		if err := s.clearActiveOrganizationRebuildCursor(ctx); err != nil {
			return nil, false, err
		}
	} else if err := s.setActiveOrganizationRebuildCursor(ctx, scanCursor); err != nil {
		return nil, true, err
	}

	organizations, err := s.activeOrganizations(ctx)
	if err != nil {
		return nil, !complete, err
	}
	if s.logger != nil {
		s.logger.Debug(
			"advanced active organization rebuild",
			"discovered", len(discovered),
			"indexed", len(organizations),
			"cursor", scanCursor,
			"complete", complete,
		)
	}
	return organizations, !complete, nil
}

func (s *Store) cleanupLegacyOrganizationIndex(ctx context.Context) {
	if strings.TrimSpace(s.legacyOrgIndexKey) == "" {
		return
	}
	if err := s.client.Del(ctx, s.legacyOrgIndexKey).Err(); err != nil && !errors.Is(err, goredis.Nil) && s.logger != nil {
		s.logger.Warn(
			"failed to remove legacy redis organization index",
			"key", s.legacyOrgIndexKey,
			"error", err,
		)
	}
}

func (s *Store) LoadSignalPayload(ctx context.Context, organization string) ([]byte, error) {
	payload, err := s.client.HGet(ctx, s.OrganizationKey(organization), s.hashField).Result()
	if errors.Is(err, goredis.Nil) {
		return []byte{}, nil
	}
	if err != nil {
		return nil, fmt.Errorf("read redis hash for organization %s: %w", organization, err)
	}
	return []byte(payload), nil
}

func (s *Store) LoadSignalLogs(ctx context.Context, organization string) ([]models.SignalLog, error) {
	payload, err := s.LoadSignalPayload(ctx, organization)
	if err != nil {
		return nil, err
	}

	logs, err := models.DecodeSignalLogsPayload(payload)
	if err != nil {
		return nil, fmt.Errorf("decode redis payload for organization %s: %w", organization, err)
	}
	return logs, nil
}

func (s *Store) SaveSignalLogs(ctx context.Context, organization string, logs []models.SignalLog) error {
	payload, err := models.MarshalSignalLogsPayload(logs)
	if err != nil {
		return fmt.Errorf("marshal redis payload for organization %s: %w", organization, err)
	}
	if err := s.client.HSet(ctx, s.OrganizationKey(organization), s.hashField, payload).Err(); err != nil {
		return fmt.Errorf("write redis hash for organization %s: %w", organization, err)
	}
	if err := s.indexActiveOrganization(ctx, organization); err != nil {
		return err
	}
	return nil
}

func (s *Store) DeleteSignalLogs(ctx context.Context, organization string) error {
	orgKey := s.OrganizationKey(organization)
	if err := s.client.HDel(ctx, orgKey, s.hashField).Err(); err != nil {
		return fmt.Errorf("delete signal logs field for organization %s: %w", organization, err)
	}
	if err := s.cleanupOrganizationHashIfEmpty(ctx, orgKey); err != nil {
		return fmt.Errorf("cleanup redis key for organization %s: %w", organization, err)
	}
	if err := s.cleanupOrganizationMembership(ctx, organization); err != nil {
		return fmt.Errorf("cleanup organization index for organization %s: %w", organization, err)
	}
	return nil
}

func (s *Store) ReadSignalStream(ctx context.Context, lastID string) ([]models.SignalStreamEvent, string, error) {
	if !s.signalStreamEnabled {
		return nil, strings.TrimSpace(lastID), nil
	}

	currentID := strings.TrimSpace(lastID)
	if currentID == "" {
		currentID = "0-0"
	}

	events := make([]models.SignalStreamEvent, 0)
	count := int64(s.signalStreamBatchSize)
	if count <= 0 {
		count = 1000
	}

	for {
		streams, err := s.client.XRead(ctx, &goredis.XReadArgs{
			Streams: []string{s.signalStreamKey, currentID},
			Count:   count,
		}).Result()
		if errors.Is(err, goredis.Nil) {
			return events, currentID, nil
		}
		if err != nil {
			return nil, currentID, fmt.Errorf("read redis signal stream %s: %w", s.signalStreamKey, err)
		}
		if len(streams) == 0 || len(streams[0].Messages) == 0 {
			return events, currentID, nil
		}

		for _, message := range streams[0].Messages {
			payloadRaw, ok := message.Values["payload"]
			if !ok {
				continue
			}
			payload := strings.TrimSpace(fmt.Sprint(payloadRaw))
			if payload == "" {
				continue
			}

			var event models.SignalStreamEvent
			if err := json.Unmarshal([]byte(payload), &event); err != nil {
				return nil, currentID, fmt.Errorf("decode signal stream payload %s: %w", message.ID, err)
			}
			events = append(events, event)
			currentID = message.ID
		}

		if len(streams[0].Messages) < int(count) {
			return events, currentID, nil
		}
	}
}

func (s *Store) TrimSignalStream(ctx context.Context, minID string) (int64, error) {
	return s.trimSignalStreamKeys(ctx, minID, []string{s.signalStreamKey})
}

func SignalPayloadSignature(payload []byte) string {
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

func (s *Store) PublishResult(ctx context.Context, result *models.CorrelationResult) error {
	if result == nil {
		return fmt.Errorf("result cannot be nil")
	}

	payload, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("marshal correlation result: %w", err)
	}
	resultKey := s.ResultKey(result.OrganizationID)
	pipe := s.client.TxPipeline()
	pipe.LPush(ctx, resultKey, payload)
	if s.resultListMaxLen > 0 {
		pipe.LTrim(ctx, resultKey, 0, int64(s.resultListMaxLen-1))
	}
	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("publish correlation result for organization %s: %w", result.OrganizationID, err)
	}

	if s.logger != nil {
		s.logger.Debug(
			"published correlation result",
			"organization", result.OrganizationID,
			"rule_id", result.RuleID,
			"result_list_max_len", s.resultListMaxLen,
		)
	}
	return nil
}

func (s *Store) LoadIncident(ctx context.Context, organization, incidentID string) (*models.IncidentState, error) {
	payload, err := s.client.HGet(ctx, s.ActiveIncidentStateKey(organization), incidentID).Result()
	if errors.Is(err, goredis.Nil) {
		return s.loadLegacyIncident(ctx, organization, incidentID)
	}
	if err != nil {
		return nil, fmt.Errorf("load active incident %s for organization %s: %w", incidentID, organization, err)
	}
	state, err := decodeIncidentStatePayload([]byte(payload))
	if err != nil {
		return nil, fmt.Errorf("decode active incident %s for organization %s: %w", incidentID, organization, err)
	}
	return &state, nil
}

func (s *Store) ListActiveIncidents(ctx context.Context, organization string) ([]models.IncidentState, error) {
	incidents, found, err := s.loadActiveIncidentsFromStateHash(ctx, organization)
	if err != nil {
		return nil, err
	}
	if found {
		return incidents, nil
	}

	legacyHashIncidents, found, err := s.loadActiveIncidentsFromHash(ctx, organization)
	if err != nil {
		return nil, err
	}
	if found {
		if err := s.saveActiveIncidentsToStateHash(ctx, organization, legacyHashIncidents); err != nil {
			return nil, err
		}
		if err := s.client.HDel(ctx, s.OrganizationKey(organization), s.incidentField).Err(); err != nil && !errors.Is(err, goredis.Nil) {
			return nil, fmt.Errorf("remove legacy active incident field for organization %s: %w", organization, err)
		}
		if err := s.cleanupOrganizationHashIfEmpty(ctx, s.OrganizationKey(organization)); err != nil {
			return nil, fmt.Errorf("cleanup organization hash for organization %s: %w", organization, err)
		}
		return legacyHashIncidents, nil
	}

	legacyIncidents, err := s.loadLegacyActiveIncidents(ctx, organization)
	if err != nil {
		return nil, err
	}
	if len(legacyIncidents) == 0 {
		return []models.IncidentState{}, nil
	}
	if err := s.saveActiveIncidentsToStateHash(ctx, organization, legacyIncidents); err != nil {
		return nil, err
	}
	if err := s.deleteLegacyIncidentStorage(ctx, organization, legacyIncidents); err != nil && s.logger != nil {
		s.logger.Warn(
			"failed to clean legacy incident redis keys after migration",
			"organization", organization,
			"error", err,
		)
	}
	return legacyIncidents, nil
}

func (s *Store) SaveIncident(ctx context.Context, state *models.IncidentState, ttl time.Duration) error {
	if state == nil {
		return fmt.Errorf("incident state cannot be nil")
	}
	if state.IncidentID == "" {
		return fmt.Errorf("incident id must not be empty")
	}
	if state.OrganizationID == "" {
		return fmt.Errorf("organization id must not be empty")
	}

	_ = ttl

	payload, err := json.Marshal(state)
	if err != nil {
		return fmt.Errorf("marshal active incident %s for organization %s: %w", state.IncidentID, state.OrganizationID, err)
	}

	pipe := s.client.TxPipeline()
	pipe.HSet(ctx, s.ActiveIncidentStateKey(state.OrganizationID), state.IncidentID, payload)
	pipe.Del(ctx, s.legacyActiveIncidentLastSeenKey(state.OrganizationID))
	pipe.SAdd(ctx, s.activeOrgSetKey, state.OrganizationID)
	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("save active incident %s for organization %s: %w", state.IncidentID, state.OrganizationID, err)
	}

	if err := s.deleteLegacyIncidentStorage(ctx, state.OrganizationID, []models.IncidentState{*state}); err != nil && s.logger != nil {
		s.logger.Warn(
			"failed to clean legacy incident redis keys after save",
			"organization", state.OrganizationID,
			"incident_id", state.IncidentID,
			"error", err,
		)
	}
	if err := s.client.HDel(ctx, s.OrganizationKey(state.OrganizationID), s.incidentField).Err(); err != nil && !errors.Is(err, goredis.Nil) {
		return fmt.Errorf("remove legacy active incident field for organization %s: %w", state.OrganizationID, err)
	}
	if err := s.cleanupOrganizationHashIfEmpty(ctx, s.OrganizationKey(state.OrganizationID)); err != nil {
		return fmt.Errorf("cleanup organization hash for organization %s: %w", state.OrganizationID, err)
	}
	return nil
}

func (s *Store) DeleteIncident(ctx context.Context, organization, incidentID string) error {
	pipe := s.client.TxPipeline()
	pipe.HDel(ctx, s.ActiveIncidentStateKey(organization), incidentID)
	pipe.Del(ctx, s.legacyActiveIncidentLastSeenKey(organization))
	pipe.Del(ctx, s.IncidentKey(organization, incidentID))
	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("delete active incident %s for organization %s: %w", incidentID, organization, err)
	}

	if err := s.deleteLegacyIncidentStorage(ctx, organization, []models.IncidentState{{IncidentID: incidentID}}); err != nil && s.logger != nil {
		s.logger.Warn(
			"failed to clean legacy incident redis keys after delete",
			"organization", organization,
			"incident_id", incidentID,
			"error", err,
		)
	}
	if err := s.cleanupIncidentStateKeysIfEmpty(ctx, organization); err != nil {
		return err
	}
	if err := s.client.HDel(ctx, s.OrganizationKey(organization), s.incidentField).Err(); err != nil && !errors.Is(err, goredis.Nil) {
		return fmt.Errorf("remove legacy active incident field for organization %s: %w", organization, err)
	}
	if err := s.cleanupOrganizationHashIfEmpty(ctx, s.OrganizationKey(organization)); err != nil {
		return fmt.Errorf("cleanup organization hash for organization %s: %w", organization, err)
	}
	if err := s.cleanupOrganizationMembership(ctx, organization); err != nil {
		return err
	}
	return nil
}

func (s *Store) organizationHashFieldsExist(ctx context.Context, key string) (bool, bool, error) {
	signalsExist, err := s.client.HExists(ctx, key, s.hashField).Result()
	if err != nil {
		if isWrongType(err) {
			return false, false, nil
		}
		return false, false, err
	}
	incidentsExist, err := s.client.HExists(ctx, key, s.incidentField).Result()
	if err != nil {
		if isWrongType(err) {
			return false, false, nil
		}
		return false, false, err
	}
	return signalsExist, incidentsExist, nil
}

func (s *Store) cleanupOrganizationHashIfEmpty(ctx context.Context, organizationKey string) error {
	fieldCount, err := s.client.HLen(ctx, organizationKey).Result()
	if err != nil {
		if isWrongType(err) || errors.Is(err, goredis.Nil) {
			return nil
		}
		return err
	}
	if fieldCount == 0 {
		if err := s.client.Del(ctx, organizationKey).Err(); err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) cleanupIncidentStateKeysIfEmpty(ctx context.Context, organization string) error {
	stateKey := s.ActiveIncidentStateKey(organization)
	fieldCount, err := s.client.HLen(ctx, stateKey).Result()
	if err != nil {
		if isWrongType(err) || errors.Is(err, goredis.Nil) {
			return nil
		}
		return fmt.Errorf("inspect active incident state hash for organization %s: %w", organization, err)
	}
	if fieldCount > 0 {
		return nil
	}

	pipe := s.client.TxPipeline()
	pipe.Del(ctx, stateKey)
	pipe.Del(ctx, s.legacyActiveIncidentLastSeenKey(organization))
	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("cleanup active incident state keys for organization %s: %w", organization, err)
	}
	return nil
}

func (s *Store) cleanupOrganizationMembership(ctx context.Context, organization string) error {
	signalsExist, err := s.client.HExists(ctx, s.OrganizationKey(organization), s.hashField).Result()
	if err != nil && !errors.Is(err, goredis.Nil) && !isWrongType(err) {
		return fmt.Errorf("inspect signal payload for organization %s: %w", organization, err)
	}
	incidentCount, err := s.client.HLen(ctx, s.ActiveIncidentStateKey(organization)).Result()
	if err != nil && !errors.Is(err, goredis.Nil) && !isWrongType(err) {
		return fmt.Errorf("inspect active incident count for organization %s: %w", organization, err)
	}
	if signalsExist || incidentCount > 0 {
		return nil
	}
	if err := s.client.SRem(ctx, s.activeOrgSetKey, organization).Err(); err != nil && !errors.Is(err, goredis.Nil) {
		return fmt.Errorf("remove organization %s from active organization index: %w", organization, err)
	}
	return nil
}

func (s *Store) loadActiveIncidentsFromHash(ctx context.Context, organization string) ([]models.IncidentState, bool, error) {
	payload, err := s.client.HGet(ctx, s.OrganizationKey(organization), s.incidentField).Result()
	if errors.Is(err, goredis.Nil) {
		return []models.IncidentState{}, false, nil
	}
	if err != nil {
		return nil, false, fmt.Errorf("load active incidents for organization %s: %w", organization, err)
	}
	if strings.TrimSpace(payload) == "" {
		return []models.IncidentState{}, true, nil
	}

	var rawIncidents []json.RawMessage
	if err := json.Unmarshal([]byte(payload), &rawIncidents); err != nil {
		return nil, true, fmt.Errorf("decode active incidents for organization %s: %w", organization, err)
	}
	incidents := make([]models.IncidentState, 0, len(rawIncidents))
	for _, raw := range rawIncidents {
		state, err := decodeIncidentStatePayload(raw)
		if err != nil {
			return nil, true, fmt.Errorf("decode active incidents for organization %s: %w", organization, err)
		}
		incidents = append(incidents, state)
	}
	sort.Slice(incidents, func(i, j int) bool {
		return incidents[i].IncidentID < incidents[j].IncidentID
	})
	return incidents, true, nil
}

func (s *Store) loadActiveIncidentsFromStateHash(ctx context.Context, organization string) ([]models.IncidentState, bool, error) {
	values, err := s.client.HGetAll(ctx, s.ActiveIncidentStateKey(organization)).Result()
	if errors.Is(err, goredis.Nil) {
		return []models.IncidentState{}, false, nil
	}
	if err != nil {
		return nil, false, fmt.Errorf("load active incident state hash for organization %s: %w", organization, err)
	}
	if len(values) == 0 {
		return []models.IncidentState{}, false, nil
	}

	incidents := make([]models.IncidentState, 0, len(values))
	for incidentID, payload := range values {
		if strings.TrimSpace(payload) == "" {
			continue
		}

		state, err := decodeIncidentStatePayload([]byte(payload))
		if err != nil {
			return nil, true, fmt.Errorf("decode active incident %s for organization %s: %w", incidentID, organization, err)
		}
		incidents = append(incidents, state)
	}
	sort.Slice(incidents, func(i, j int) bool {
		return incidents[i].IncidentID < incidents[j].IncidentID
	})
	return incidents, true, nil
}

func (s *Store) saveActiveIncidentsToStateHash(ctx context.Context, organization string, incidents []models.IncidentState) error {
	stateKey := s.ActiveIncidentStateKey(organization)
	legacyLastSeenKey := s.legacyActiveIncidentLastSeenKey(organization)
	if len(incidents) == 0 {
		pipe := s.client.TxPipeline()
		pipe.Del(ctx, stateKey)
		pipe.Del(ctx, legacyLastSeenKey)
		if _, err := pipe.Exec(ctx); err != nil {
			return fmt.Errorf("delete active incidents for organization %s: %w", organization, err)
		}
		return s.cleanupOrganizationMembership(ctx, organization)
	}

	payloads := make(map[string]any, len(incidents))
	for _, incident := range incidents {
		payload, err := json.Marshal(incident)
		if err != nil {
			return fmt.Errorf("marshal active incident %s for organization %s: %w", incident.IncidentID, organization, err)
		}
		payloads[incident.IncidentID] = payload
	}

	pipe := s.client.TxPipeline()
	pipe.Del(ctx, stateKey)
	pipe.Del(ctx, legacyLastSeenKey)
	pipe.HSet(ctx, stateKey, payloads)
	pipe.SAdd(ctx, s.activeOrgSetKey, organization)
	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("save active incident state hash for organization %s: %w", organization, err)
	}
	return nil
}

func (s *Store) loadLegacyActiveIncidents(ctx context.Context, organization string) ([]models.IncidentState, error) {
	incidentIDs, err := s.client.SMembers(ctx, s.IncidentIndexKey(organization)).Result()
	if errors.Is(err, goredis.Nil) {
		return []models.IncidentState{}, nil
	}
	if err != nil {
		return nil, fmt.Errorf("list legacy active incidents for organization %s: %w", organization, err)
	}

	incidents := make([]models.IncidentState, 0, len(incidentIDs))
	for _, incidentID := range incidentIDs {
		payload, err := s.client.Get(ctx, s.IncidentKey(organization, incidentID)).Result()
		if errors.Is(err, goredis.Nil) {
			continue
		}
		if err != nil {
			return nil, fmt.Errorf("load legacy incident %s for organization %s: %w", incidentID, organization, err)
		}
		if strings.TrimSpace(payload) == "" {
			continue
		}

		state, err := decodeIncidentStatePayload([]byte(payload))
		if err != nil {
			return nil, fmt.Errorf("decode legacy incident %s for organization %s: %w", incidentID, organization, err)
		}
		incidents = append(incidents, state)
	}
	sort.Slice(incidents, func(i, j int) bool {
		return incidents[i].IncidentID < incidents[j].IncidentID
	})
	return incidents, nil
}

func (s *Store) loadLegacyIncident(ctx context.Context, organization, incidentID string) (*models.IncidentState, error) {
	incidents, err := s.ListActiveIncidents(ctx, organization)
	if err != nil {
		return nil, err
	}
	for _, state := range incidents {
		if state.IncidentID == incidentID {
			cloned := state
			return &cloned, nil
		}
	}
	return nil, nil
}

type incidentStatePayload struct {
	IncidentID          string                   `json:"incident_id"`
	OrganizationID      string                   `json:"organization_id"`
	RuleID              string                   `json:"rule_id"`
	Status              string                   `json:"status"`
	FirstSeen           time.Time                `json:"first_seen"`
	LastSeen            time.Time                `json:"last_seen"`
	LastResultSignature string                   `json:"last_result_signature"`
	GroupByValues       map[string]string        `json:"group_by_values,omitempty"`
	Snapshot            models.IncidentSnapshot  `json:"snapshot"`
	LatestResult        models.CorrelationResult `json:"latest_result"`
}

func decodeIncidentStatePayload(payload []byte) (models.IncidentState, error) {
	var decoded incidentStatePayload
	if err := json.Unmarshal(payload, &decoded); err != nil {
		return models.IncidentState{}, err
	}

	snapshot := decoded.Snapshot
	if isZeroIncidentSnapshot(snapshot) {
		snapshot = incidentSnapshotFromResult(decoded.LatestResult)
	}

	return models.IncidentState{
		IncidentID:          decoded.IncidentID,
		OrganizationID:      decoded.OrganizationID,
		RuleID:              decoded.RuleID,
		Status:              decoded.Status,
		FirstSeen:           decoded.FirstSeen.UTC(),
		LastSeen:            decoded.LastSeen.UTC(),
		LastResultSignature: decoded.LastResultSignature,
		GroupByValues:       decoded.GroupByValues,
		Snapshot:            snapshot,
	}, nil
}

func incidentSnapshotFromResult(result models.CorrelationResult) models.IncidentSnapshot {
	return models.IncidentSnapshot{
		SchemaVersion:  result.SchemaVersion,
		LogID:          cloneResultLogs(result.LogID),
		RuleCompletion: result.RuleCompletion,
		SequenceMatch:  result.SequenceMatch,
		MatchedAt:      result.MatchedAt.UTC(),
		CorrelatedAt:   result.CorrelatedAt.UTC(),
		Audit:          cloneMatchAudit(result.Audit),
	}
}

func isZeroIncidentSnapshot(snapshot models.IncidentSnapshot) bool {
	return snapshot.SchemaVersion == 0 &&
		len(snapshot.LogID) == 0 &&
		snapshot.RuleCompletion == 0 &&
		snapshot.SequenceMatch == 0 &&
		snapshot.MatchedAt.IsZero() &&
		snapshot.CorrelatedAt.IsZero() &&
		snapshot.Audit == nil
}

func cloneResultLogs(entries []models.ResultLog) []models.ResultLog {
	if len(entries) == 0 {
		return nil
	}
	cloned := make([]models.ResultLog, len(entries))
	for idx, entry := range entries {
		cloned[idx] = entry
		if len(entry.HostIPs) > 0 {
			cloned[idx].HostIPs = append([]string(nil), entry.HostIPs...)
		}
	}
	return cloned
}

func cloneMatchAudit(audit *models.MatchAudit) *models.MatchAudit {
	if audit == nil {
		return nil
	}

	cloned := *audit
	if len(audit.GroupBy) > 0 {
		cloned.GroupBy = append([]string(nil), audit.GroupBy...)
	}
	if len(audit.GroupByValues) > 0 {
		cloned.GroupByValues = make(map[string]string, len(audit.GroupByValues))
		for key, value := range audit.GroupByValues {
			cloned.GroupByValues[key] = value
		}
	}
	if len(audit.RequiredMetadata) > 0 {
		cloned.RequiredMetadata = make(map[string]string, len(audit.RequiredMetadata))
		for key, value := range audit.RequiredMetadata {
			cloned.RequiredMetadata[key] = value
		}
	}
	if len(audit.NegativeSignals) > 0 {
		cloned.NegativeSignals = append([]string(nil), audit.NegativeSignals...)
	}
	if len(audit.DeduplicationKey) > 0 {
		cloned.DeduplicationKey = append([]string(nil), audit.DeduplicationKey...)
	}
	if len(audit.MatchedLogIDs) > 0 {
		cloned.MatchedLogIDs = append([]string(nil), audit.MatchedLogIDs...)
	}
	if len(audit.MatchedSignals) > 0 {
		cloned.MatchedSignals = append([]string(nil), audit.MatchedSignals...)
	}
	if len(audit.Steps) > 0 {
		cloned.Steps = make([]models.MatchStepAudit, len(audit.Steps))
		for idx, step := range audit.Steps {
			cloned.Steps[idx] = step
			if len(step.MatchedLogIDs) > 0 {
				cloned.Steps[idx].MatchedLogIDs = append([]string(nil), step.MatchedLogIDs...)
			}
		}
	}
	return &cloned
}

func (s *Store) deleteLegacyIncidentStorage(ctx context.Context, organization string, incidents []models.IncidentState) error {
	pipe := s.client.TxPipeline()
	for _, incident := range incidents {
		if strings.TrimSpace(incident.IncidentID) == "" {
			continue
		}
		pipe.Del(ctx, s.IncidentKey(organization, incident.IncidentID))
	}
	pipe.Del(ctx, s.IncidentIndexKey(organization))
	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("cleanup legacy incident storage for organization %s: %w", organization, err)
	}
	return nil
}

func (s *Store) activeOrganizations(ctx context.Context) ([]string, error) {
	if strings.TrimSpace(s.activeOrgSetKey) == "" {
		return nil, nil
	}
	organizations, err := s.client.SMembers(ctx, s.activeOrgSetKey).Result()
	if errors.Is(err, goredis.Nil) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("load active organization index %s: %w", s.activeOrgSetKey, err)
	}
	organizations = compactStrings(organizations)
	sort.Strings(organizations)
	return organizations, nil
}

func (s *Store) scanOrganizationFromKey(key string) (string, bool) {
	prefix := s.keyPrefix + ":"
	if !strings.HasPrefix(key, prefix) {
		return "", false
	}
	trimmed := strings.TrimPrefix(key, prefix)
	switch {
	case trimmed == "":
		return "", false
	case !strings.Contains(trimmed, ":"):
		return trimmed, true
	case strings.HasSuffix(trimmed, ":active_incident_states"):
		return strings.TrimSuffix(trimmed, ":active_incident_states"), false
	case strings.HasSuffix(trimmed, ":active_incidents"):
		return strings.TrimSuffix(trimmed, ":active_incidents"), false
	case strings.HasSuffix(trimmed, ":active_incidents_by_last_seen"):
		return strings.TrimSuffix(trimmed, ":active_incidents_by_last_seen"), false
	case strings.Contains(trimmed, ":incident:"):
		return strings.SplitN(trimmed, ":incident:", 2)[0], false
	default:
		return "", false
	}
}

func (s *Store) activeOrganizationRebuildCursor(ctx context.Context) (uint64, bool, error) {
	if strings.TrimSpace(s.activeOrgCursorKey) == "" {
		return 0, false, nil
	}

	cursorValue, err := s.client.Get(ctx, s.activeOrgCursorKey).Result()
	if errors.Is(err, goredis.Nil) {
		return 0, false, nil
	}
	if err != nil {
		return 0, false, fmt.Errorf("load active organization rebuild cursor %s: %w", s.activeOrgCursorKey, err)
	}

	cursorValue = strings.TrimSpace(cursorValue)
	if cursorValue == "" {
		return 0, false, nil
	}

	cursor, err := strconv.ParseUint(cursorValue, 10, 64)
	if err != nil {
		return 0, false, fmt.Errorf("parse active organization rebuild cursor %s: %w", s.activeOrgCursorKey, err)
	}
	return cursor, true, nil
}

func (s *Store) setActiveOrganizationRebuildCursor(ctx context.Context, cursor uint64) error {
	if strings.TrimSpace(s.activeOrgCursorKey) == "" {
		return nil
	}
	if err := s.client.Set(ctx, s.activeOrgCursorKey, fmt.Sprintf("%d", cursor), 0).Err(); err != nil {
		return fmt.Errorf("save active organization rebuild cursor %s: %w", s.activeOrgCursorKey, err)
	}
	return nil
}

func (s *Store) clearActiveOrganizationRebuildCursor(ctx context.Context) error {
	if strings.TrimSpace(s.activeOrgCursorKey) == "" {
		return nil
	}
	if err := s.client.Del(ctx, s.activeOrgCursorKey).Err(); err != nil && !errors.Is(err, goredis.Nil) {
		return fmt.Errorf("clear active organization rebuild cursor %s: %w", s.activeOrgCursorKey, err)
	}
	return nil
}

func (s *Store) shouldYieldActiveOrganizationRebuild(ctx context.Context) bool {
	deadline, ok := ctx.Deadline()
	if !ok {
		return false
	}
	return time.Until(deadline) <= activeOrgRebuildDeadlineReserve
}

func isWrongType(err error) bool {
	return strings.Contains(strings.ToUpper(err.Error()), "WRONGTYPE")
}

func sortedKeys(values map[string]struct{}) []string {
	if len(values) == 0 {
		return nil
	}
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func compactStrings(values []string) []string {
	result := make([]string, 0, len(values))
	for _, value := range values {
		trimmed := strings.TrimSpace(value)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

func stringSliceToAny(values []string) []any {
	result := make([]any, 0, len(values))
	for _, value := range values {
		if strings.TrimSpace(value) == "" {
			continue
		}
		result = append(result, value)
	}
	return result
}

func (s *Store) indexActiveOrganization(ctx context.Context, organization string) error {
	trimmed := strings.TrimSpace(organization)
	if trimmed == "" {
		return nil
	}
	if err := s.client.SAdd(ctx, s.activeOrgSetKey, trimmed).Err(); err != nil {
		return fmt.Errorf("index active organization %s: %w", trimmed, err)
	}
	return nil
}

func (s *Store) legacyActiveIncidentLastSeenKey(organization string) string {
	return fmt.Sprintf("%s:%s:active_incidents_by_last_seen", s.keyPrefix, organization)
}

func randomToken() (string, error) {
	bytes := make([]byte, 16)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}
