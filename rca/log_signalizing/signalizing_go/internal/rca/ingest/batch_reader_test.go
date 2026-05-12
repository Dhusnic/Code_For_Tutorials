package ingest

import "testing"

type stubSearchClient struct {
	responses []map[string]any
	calls     []map[string]any
}

func (s *stubSearchClient) Search(index string, body map[string]any) (map[string]any, error) {
	s.calls = append(s.calls, map[string]any{"index": index, "body": body})
	response := s.responses[0]
	s.responses = s.responses[1:]
	return response, nil
}

func TestBatchReaderUsesConfiguredIndexAndStableSort(t *testing.T) {
	client := &stubSearchClient{
		responses: []map[string]any{
			{"hits": map[string]any{"hits": []any{}}},
		},
	}
	reader := NewBatchReader(client, "linux-*", 250, "@timestamp", "now-15m", nil, true)

	hits, err := reader.IterHits(nil)
	if err != nil {
		t.Fatalf("iter hits: %v", err)
	}
	if len(hits) != 0 {
		t.Fatalf("expected no hits, got %d", len(hits))
	}

	if client.calls[0]["index"] != "linux-*" {
		t.Fatalf("unexpected index: %v", client.calls[0]["index"])
	}
	body := client.calls[0]["body"].(map[string]any)
	sortValue := body["sort"].([]any)
	if len(sortValue) != 2 {
		t.Fatalf("unexpected sort: %#v", sortValue)
	}
	if body["track_total_hits"] != false {
		t.Fatalf("expected track_total_hits=false, got %v", body["track_total_hits"])
	}
	query := body["query"].(map[string]any)
	boolean := query["bool"].(map[string]any)
	mustNot := boolean["must_not"].([]any)
	if len(mustNot) != 2 {
		t.Fatalf("unexpected must_not: %#v", mustNot)
	}
}

func TestBatchReaderIgnoresLegacySingleValueCheckpointSort(t *testing.T) {
	client := &stubSearchClient{
		responses: []map[string]any{
			{"hits": map[string]any{"hits": []any{}}},
		},
	}
	reader := NewBatchReader(client, "linux-*", 250, "@timestamp", "now-15m", nil, true)

	if _, err := reader.IterHits([]any{"2026-02-18T00:00:00Z"}); err != nil {
		t.Fatalf("iter hits: %v", err)
	}

	body := client.calls[0]["body"].(map[string]any)
	if _, ok := body["search_after"]; ok {
		t.Fatal("expected legacy single-value search_after to be omitted")
	}
}

func TestBatchReaderIterateHitsStreamsAcrossPages(t *testing.T) {
	client := &stubSearchClient{
		responses: []map[string]any{
			{
				"hits": map[string]any{
					"hits": []any{
						map[string]any{
							"_id":   "doc-1",
							"sort":  []any{"2026-05-05T06:20:00Z", 1},
							"_source": map[string]any{"message": "first"},
						},
					},
				},
			},
			{
				"hits": map[string]any{
					"hits": []any{
						map[string]any{
							"_id":   "doc-2",
							"sort":  []any{"2026-05-05T06:20:01Z", 2},
							"_source": map[string]any{"message": "second"},
						},
					},
				},
			},
			{"hits": map[string]any{"hits": []any{}}},
		},
	}
	reader := NewBatchReader(client, "linux-*", 250, "@timestamp", "now-15m", nil, true)

	seen := make([]string, 0, 2)
	if err := reader.IterateHits(nil, func(hit map[string]any) error {
		seen = append(seen, hit["_id"].(string))
		return nil
	}); err != nil {
		t.Fatalf("iterate hits: %v", err)
	}

	if len(seen) != 2 || seen[0] != "doc-1" || seen[1] != "doc-2" {
		t.Fatalf("unexpected streamed hits: %#v", seen)
	}
	if len(client.calls) != 3 {
		t.Fatalf("expected 3 search calls, got %d", len(client.calls))
	}
	secondBody := client.calls[1]["body"].(map[string]any)
	searchAfter, ok := secondBody["search_after"].([]any)
	if !ok || len(searchAfter) != 2 {
		t.Fatalf("expected search_after on second page, got %#v", secondBody["search_after"])
	}
	if searchAfter[0] != "2026-05-05T06:20:00Z" || searchAfter[1] != 1 {
		t.Fatalf("unexpected search_after values: %#v", searchAfter)
	}
}
