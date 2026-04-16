package es

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	elasticsearch "github.com/elastic/go-elasticsearch/v8"

	"rca/internal/rca/config"
)

// Client wraps the official Elasticsearch client with the shapes used by the migrated code.
type Client struct {
	raw            *elasticsearch.Client
	requestTimeout time.Duration
}

// NewClient builds an Elasticsearch client from application config.
func NewClient(cfg config.ElasticsearchConfig) (*Client, error) {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	if !cfg.VerifyCerts {
		transport.TLSClientConfig = &tls.Config{InsecureSkipVerify: true} //nolint:gosec // parity with Python verify_certs=False
	}

	clientConfig := elasticsearch.Config{
		Addresses: cfg.Hosts,
		Username:  derefString(cfg.Username),
		Password:  derefString(cfg.Password),
		APIKey:    derefString(cfg.APIKey),
		Transport: transport,
	}

	raw, err := elasticsearch.NewClient(clientConfig)
	if err != nil {
		return nil, err
	}
	return &Client{
		raw:            raw,
		requestTimeout: time.Duration(cfg.RequestTimeoutSeconds) * time.Second,
	}, nil
}

// Search executes a search request and returns the decoded JSON response.
func (c *Client) Search(index string, body map[string]any) (map[string]any, error) {
	ctx, cancel := c.requestContext()
	defer cancel()
	response, err := c.raw.Search(
		c.raw.Search.WithIndex(index),
		c.raw.Search.WithBody(mustBody(body)),
		c.raw.Search.WithContext(ctx),
	)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	return decodeResponse(response.Body)
}

// Count executes a count request and returns the decoded JSON response.
func (c *Client) Count(index string, body map[string]any) (map[string]any, error) {
	ctx, cancel := c.requestContext()
	defer cancel()
	response, err := c.raw.Count(
		c.raw.Count.WithIndex(index),
		c.raw.Count.WithBody(mustBody(body)),
		c.raw.Count.WithContext(ctx),
	)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	return decodeResponse(response.Body)
}

// IndicesGet expands an index pattern and returns the decoded JSON response.
func (c *Client) IndicesGet(index string) (map[string]any, error) {
	ctx, cancel := c.requestContext()
	defer cancel()
	response, err := c.raw.Indices.Get(
		[]string{index},
		c.raw.Indices.Get.WithAllowNoIndices(true),
		c.raw.Indices.Get.WithIgnoreUnavailable(true),
		c.raw.Indices.Get.WithExpandWildcards("open,hidden"),
		c.raw.Indices.Get.WithContext(ctx),
	)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	return decodeResponse(response.Body)
}

// Bulk submits NDJSON bulk actions and returns success count plus item errors.
func (c *Client) Bulk(actions []map[string]any) (int, []map[string]any, error) {
	var payload bytes.Buffer
	for _, action := range actions {
		opType := fmt.Sprint(action["_op_type"])
		switch opType {
		case "update":
			meta := map[string]any{
				"update": map[string]any{
					"_index": action["_index"],
					"_id":    action["_id"],
				},
			}
			body := map[string]any{
				"doc":           action["doc"],
				"doc_as_upsert": action["doc_as_upsert"],
			}
			writeJSONLine(&payload, meta)
			writeJSONLine(&payload, body)
		case "index":
			meta := map[string]any{
				"index": map[string]any{
					"_index": action["_index"],
					"_id":    action["_id"],
				},
			}
			writeJSONLine(&payload, meta)
			writeJSONLine(&payload, action["_source"])
		default:
			return 0, nil, fmt.Errorf("unsupported bulk action op_type: %s", opType)
		}
	}

	ctx, cancel := c.requestContext()
	defer cancel()
	response, err := c.raw.Bulk(bytes.NewReader(payload.Bytes()), c.raw.Bulk.WithContext(ctx))
	if err != nil {
		return 0, nil, err
	}
	defer response.Body.Close()

	var decoded map[string]any
	if err := json.NewDecoder(response.Body).Decode(&decoded); err != nil {
		return 0, nil, err
	}

	items, _ := decoded["items"].([]any)
	success := 0
	errors := make([]map[string]any, 0)
	for _, itemRaw := range items {
		item, ok := itemRaw.(map[string]any)
		if !ok {
			continue
		}
		for opType, payloadRaw := range item {
			payloadMap, ok := payloadRaw.(map[string]any)
			if !ok {
				continue
			}
			status := int(numberValue(payloadMap["status"]))
			if status >= 200 && status < 300 {
				success++
				continue
			}
			errors = append(errors, map[string]any{opType: payloadMap})
		}
	}
	return success, errors, nil
}

// GetDocument fetches one document for checkpoint reads.
func (c *Client) GetDocument(index string, id string) (map[string]any, int, error) {
	ctx, cancel := c.requestContext()
	defer cancel()
	response, err := c.raw.Get(index, id, c.raw.Get.WithContext(ctx))
	if err != nil {
		return nil, 0, err
	}
	defer response.Body.Close()
	if response.StatusCode == 404 {
		return nil, 404, fmt.Errorf("not found")
	}
	decoded, err := decodeResponse(response.Body)
	if err != nil {
		return nil, response.StatusCode, err
	}
	return decoded, response.StatusCode, nil
}

// IndexDocument writes one document for checkpoint persistence.
func (c *Client) IndexDocument(index string, id string, document map[string]any) error {
	ctx, cancel := c.requestContext()
	defer cancel()
	response, err := c.raw.Index(
		index,
		mustBody(document),
		c.raw.Index.WithDocumentID(id),
		c.raw.Index.WithRefresh("false"),
		c.raw.Index.WithContext(ctx),
	)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.IsError() {
		content, _ := io.ReadAll(response.Body)
		return fmt.Errorf("elasticsearch index error: %s", string(content))
	}
	return nil
}

func mustBody(value any) io.Reader {
	encoded, _ := json.Marshal(value)
	return bytes.NewReader(encoded)
}

func writeJSONLine(buffer *bytes.Buffer, value any) {
	encoded, _ := json.Marshal(value)
	buffer.Write(encoded)
	buffer.WriteByte('\n')
}

func decodeResponse(body io.Reader) (map[string]any, error) {
	var decoded map[string]any
	if err := json.NewDecoder(body).Decode(&decoded); err != nil {
		return nil, err
	}
	return decoded, nil
}

func derefString(value *string) string {
	if value == nil {
		return ""
	}
	return *value
}

func (c *Client) requestContext() (context.Context, context.CancelFunc) {
	if c.requestTimeout <= 0 {
		return context.WithCancel(context.Background())
	}
	return context.WithTimeout(context.Background(), c.requestTimeout)
}

func numberValue(value any) float64 {
	switch typed := value.(type) {
	case int:
		return float64(typed)
	case int64:
		return float64(typed)
	case float64:
		return typed
	default:
		return 0
	}
}
