package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"gopkg.in/yaml.v3"

	"rca/internal/rca/rules"
)

func main() {
	rulesDir := flag.String("rules-dir", filepath.Join("..", "rules"), "Directory containing YAML rule files")
	flag.Parse()

	validator := rules.RuleSchemaValidator{}
	failed := false
	paths := make([]string, 0)
	_ = filepath.Walk(*rulesDir, func(path string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() && filepath.Ext(path) == ".yml" {
			paths = append(paths, path)
		}
		return nil
	})
	sort.Strings(paths)

	for _, path := range paths {
		content, err := os.ReadFile(path)
		if err != nil {
			fmt.Printf("[FAIL] %s: %v\n", path, err)
			failed = true
			continue
		}
		var payload map[string]any
		if err := yaml.Unmarshal(content, &payload); err != nil || payload == nil {
			fmt.Printf("[FAIL] %s: file root must be an object\n", path)
			failed = true
			continue
		}
		if err := validator.Validate(payload, path); err != nil {
			fmt.Printf("[FAIL] %v\n", err)
			failed = true
			continue
		}
		fmt.Printf("[OK]   %s\n", path)
	}

	if failed {
		os.Exit(1)
	}
}
