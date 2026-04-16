package legacy

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"time"

	"agenticai/desktop/internal/contracts"
	coreerrors "agenticai/desktop/internal/core/errors"
	"agenticai/desktop/internal/services"
)

type Client struct {
	baseURL       string
	httpClient    *http.Client
	logger        *slog.Logger
	ensureRunning EnsureRunningFunc
}

var _ services.DesktopService = (*Client)(nil)

type EnsureRunningFunc func(ctx context.Context) error

func NewClient(
	baseURL string,
	timeout time.Duration,
	logger *slog.Logger,
	ensureRunning EnsureRunningFunc,
) *Client {
	resolved := strings.TrimSpace(baseURL)
	if resolved == "" {
		resolved = "http://127.0.0.1:8000"
	}
	resolved = strings.TrimRight(resolved, "/")
	if timeout <= 0 {
		timeout = 180 * time.Second
	}
	return &Client{
		baseURL: resolved,
		httpClient: &http.Client{
			Timeout: timeout,
		},
		logger:        logger,
		ensureRunning: ensureRunning,
	}
}

func (c *Client) RunFullReview(ctx context.Context, request contracts.ConfigModel, async bool) (map[string]any, error) {
	return c.post(ctx, "/api/run-full-review", request, map[string]string{
		"async_job": boolString(async),
	})
}

func (c *Client) ReviewDiffs(ctx context.Context, request contracts.ConfigModel, async bool) (map[string]any, error) {
	return c.post(ctx, "/api/review-diffs", request, map[string]string{
		"async_job": boolString(async),
	})
}

func (c *Client) GenerateChanges(ctx context.Context, request contracts.ConfigModel) (map[string]any, error) {
	return c.post(ctx, "/api/generate-changes", request, nil)
}

func (c *Client) ApplyChanges(ctx context.Context, request contracts.ApplyChangesModel) (map[string]any, error) {
	return c.post(ctx, "/api/apply-changes", request, nil)
}

func (c *Client) RunStaticChecks(ctx context.Context, request contracts.StaticChecksRequestModel, async bool) (map[string]any, error) {
	return c.post(ctx, "/api/static-checks", request, map[string]string{
		"async_job": boolString(async),
	})
}

func (c *Client) GetUsageMetrics(ctx context.Context) (map[string]any, error) {
	return c.get(ctx, "/api/usage-metrics", nil)
}

func (c *Client) GetFeatureContext(ctx context.Context, request contracts.PRFeatureContextRequestModel) (map[string]any, error) {
	return c.post(ctx, "/api/pr-workflow/feature-context", request, nil)
}

func (c *Client) ListChangedFiles(ctx context.Context, request contracts.PRWorkflowBaseRequestModel) (map[string]any, error) {
	return c.post(ctx, "/api/pr-workflow/changed-files", request, nil)
}

func (c *Client) ListReviewers(ctx context.Context, request contracts.PRReviewersRequestModel) (map[string]any, error) {
	return c.post(ctx, "/api/pr-workflow/reviewers", request, nil)
}

func (c *Client) GetWorkItemFamily(ctx context.Context, request contracts.PRWorkItemFamilyRequestModel) (map[string]any, error) {
	return c.post(ctx, "/api/pr-workflow/work-item-family", request, nil)
}

func (c *Client) RaiseNewPR(ctx context.Context, request contracts.RaiseNewPRRequestModel, async bool) (map[string]any, error) {
	return c.post(ctx, "/api/pr-workflow/raise-new-pr", request, map[string]string{
		"async_job": boolString(async),
	})
}

func (c *Client) CherryPick(ctx context.Context, request contracts.CherryPickRequestModel) (map[string]any, error) {
	return c.post(ctx, "/api/pr-workflow/cherry-pick", request, nil)
}

func (c *Client) CommitAndPush(ctx context.Context, request contracts.CommitAndPushRequestModel) (map[string]any, error) {
	return c.post(ctx, "/api/pr-workflow/commit-and-push", request, nil)
}

func (c *Client) GetJob(ctx context.Context, jobID string) (map[string]any, error) {
	return c.get(ctx, fmt.Sprintf("/api/jobs/%s", url.PathEscape(strings.TrimSpace(jobID))), nil)
}

func (c *Client) ProceedJob(ctx context.Context, jobID, requestID string) (map[string]any, error) {
	payload := contracts.JobProceedRequestModel{
		RequestID: strings.TrimSpace(requestID),
	}
	return c.post(
		ctx,
		fmt.Sprintf("/api/jobs/%s/proceed", url.PathEscape(strings.TrimSpace(jobID))),
		payload,
		nil,
	)
}

func (c *Client) GetApprovalPreview(ctx context.Context, jobID, requestID string) (map[string]any, error) {
	return c.get(
		ctx,
		fmt.Sprintf("/api/jobs/%s/approval-preview", url.PathEscape(strings.TrimSpace(jobID))),
		map[string]string{"request_id": strings.TrimSpace(requestID)},
	)
}

func (c *Client) post(ctx context.Context, path string, payload any, query map[string]string) (map[string]any, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, coreerrors.Wrap("serialize_error", "failed to serialize payload", err)
	}
	return c.executeWithAutoStart(
		ctx,
		http.MethodPost,
		c.buildURL(path, query),
		body,
		map[string]string{"Content-Type": "application/json"},
	)
}

func (c *Client) get(ctx context.Context, path string, query map[string]string) (map[string]any, error) {
	return c.executeWithAutoStart(
		ctx,
		http.MethodGet,
		c.buildURL(path, query),
		nil,
		nil,
	)
}

func (c *Client) executeWithAutoStart(
	ctx context.Context,
	method string,
	fullURL string,
	body []byte,
	headers map[string]string,
) (map[string]any, error) {
	result, err := c.execute(ctx, method, fullURL, body, headers)
	if err == nil {
		return result, nil
	}
	if !isTransportOperationError(err) || c.ensureRunning == nil {
		return nil, err
	}

	if c.logger != nil {
		c.logger.Warn("legacy API unavailable; attempting desktop-managed startup", "url", fullURL)
	}
	if startErr := c.ensureRunning(ctx); startErr != nil {
		return nil, &coreerrors.OperationError{
			Code:    "legacy_startup_error",
			Message: "desktop failed to auto-start legacy API",
			Cause:   startErr,
			Details: map[string]any{
				"url": fullURL,
			},
		}
	}
	return c.execute(ctx, method, fullURL, body, headers)
}

func (c *Client) execute(
	ctx context.Context,
	method string,
	fullURL string,
	body []byte,
	headers map[string]string,
) (map[string]any, error) {
	requestBody := bytes.NewReader(body)
	request, err := http.NewRequestWithContext(ctx, method, fullURL, requestBody)
	if err != nil {
		return nil, coreerrors.Wrap("request_error", "failed to create request", err)
	}
	for key, value := range headers {
		if strings.TrimSpace(value) == "" {
			continue
		}
		request.Header.Set(key, value)
	}

	response, err := c.httpClient.Do(request)
	if err != nil {
		return nil, coreerrors.Wrap("transport_error", "legacy bridge request failed", err)
	}
	defer response.Body.Close()

	raw, readErr := io.ReadAll(response.Body)
	if readErr != nil {
		return nil, coreerrors.Wrap("response_read_error", "failed to read legacy response body", readErr)
	}

	var payload map[string]any
	if len(raw) > 0 {
		if unmarshalErr := json.Unmarshal(raw, &payload); unmarshalErr != nil {
			return nil, coreerrors.Wrap("decode_error", "failed to decode legacy response body", unmarshalErr)
		}
	}
	if payload == nil {
		payload = map[string]any{}
	}

	if response.StatusCode >= 400 {
		message := extractErrorMessage(payload)
		return nil, &coreerrors.OperationError{
			Code:    "legacy_api_error",
			Message: message,
			Details: map[string]any{
				"status_code": response.StatusCode,
				"path":        request.URL.Path,
				"response":    payload,
			},
		}
	}

	if c.logger != nil {
		c.logger.Debug(
			"legacy request completed",
			"method", request.Method,
			"path", request.URL.Path,
			"status", response.StatusCode,
		)
	}
	return payload, nil
}

func (c *Client) buildURL(path string, query map[string]string) string {
	joined := c.baseURL + "/" + strings.TrimLeft(path, "/")
	parsed, err := url.Parse(joined)
	if err != nil {
		return joined
	}
	values := parsed.Query()
	for key, value := range query {
		if strings.TrimSpace(value) == "" {
			continue
		}
		values.Set(key, value)
	}
	parsed.RawQuery = values.Encode()
	return parsed.String()
}

func boolString(value bool) string {
	if value {
		return "true"
	}
	return "false"
}

func extractErrorMessage(payload map[string]any) string {
	if payload == nil {
		return "legacy API request failed"
	}
	if detail, ok := payload["detail"]; ok {
		if text := strings.TrimSpace(fmt.Sprintf("%v", detail)); text != "" {
			return text
		}
	}
	if message, ok := payload["message"]; ok {
		if text := strings.TrimSpace(fmt.Sprintf("%v", message)); text != "" {
			return text
		}
	}
	return "legacy API request failed"
}

func isTransportOperationError(err error) bool {
	var operationErr *coreerrors.OperationError
	if !errors.As(err, &operationErr) {
		return false
	}
	return operationErr.Code == "transport_error"
}
