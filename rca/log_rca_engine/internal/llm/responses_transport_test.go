package llm

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"log_rca_engine/internal/config"
)

func TestResponsesTransportCreateResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/responses" {
			t.Fatalf("expected /responses path, got %s", r.URL.Path)
		}
		if got := r.Header.Get("Authorization"); got != "Bearer test-key" {
			t.Fatalf("expected bearer token, got %q", got)
		}

		var request responsesRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		if request.Model != "gpt-4o-mini" {
			t.Fatalf("expected model gpt-4o-mini, got %q", request.Model)
		}
		if request.MaxOutputTokens != 600 {
			t.Fatalf("expected max output tokens 600, got %d", request.MaxOutputTokens)
		}
		if request.Text.Format.Type != "json_schema" || !request.Text.Format.Strict {
			t.Fatalf("expected strict json_schema format, got %#v", request.Text.Format)
		}
		if request.Text.Format.Name != "rca_summary" {
			t.Fatalf("expected schema name rca_summary, got %q", request.Text.Format.Name)
		}

		_ = json.NewEncoder(w).Encode(map[string]any{
			"output_text": `{"root_cause":"database saturation","natural_language_summary":"The database slowed down and increased API latency.","affected_services":["checkout-api"],"evidence":["db timeout logs"],"next_checks":["check connection pool"]}`,
		})
	}))
	defer server.Close()

	transport := newResponsesTransport(config.OpenAIConfig{
		BaseURL:        server.URL,
		APIKey:         "test-key",
		RequestTimeout: 2 * time.Second,
	}, nil)

	response, err := transport.CreateResponse(context.Background(), Conversation{
		Name:            "rca_summary",
		Model:           "gpt-4o-mini",
		MaxOutputTokens: 600,
		ResponseSchema:  explanationSchema(),
		Messages: []ConversationMessage{
			{
				Role: "system",
				Content: []ContentPart{
					{Type: "input_text", Text: "Return only JSON."},
				},
			},
		},
	})
	if err != nil {
		t.Fatalf("CreateResponse() error = %v", err)
	}

	if response == "" {
		t.Fatal("expected structured response text")
	}
}
