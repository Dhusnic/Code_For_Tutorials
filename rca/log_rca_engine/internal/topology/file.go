package topology

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"log_rca_engine/internal/models"
)

type FileRepository struct {
	path string
}

func NewFileRepository(path string) *FileRepository {
	return &FileRepository{path: strings.TrimSpace(path)}
}

func (r *FileRepository) Load(ctx context.Context) (models.TopologyDocument, error) {
	if err := ctx.Err(); err != nil {
		return models.TopologyDocument{}, err
	}
	payload, err := os.ReadFile(r.path)
	if err != nil {
		return models.TopologyDocument{}, fmt.Errorf("read topology file: %w", err)
	}

	var document models.TopologyDocument
	if err := json.Unmarshal(payload, &document); err != nil {
		return models.TopologyDocument{}, fmt.Errorf("decode topology file: %w", err)
	}
	if document.Organizations == nil {
		document.Organizations = make(map[string]map[string]models.OrganizationTopology)
	}
	return document, nil
}
