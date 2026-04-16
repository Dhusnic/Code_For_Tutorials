package main

import (
	"encoding/json"
	"fmt"
	"os"

	"agenticai/desktop/internal/desktop"
)

func main() {
	app, err := desktop.New("")
	if err != nil {
		fmt.Fprintf(os.Stderr, "desktop bootstrap failed: %v\n", err)
		os.Exit(1)
	}

	health := app.Health()
	payload, _ := json.MarshalIndent(health, "", "  ")
	fmt.Println(string(payload))
	fmt.Println("Desktop scaffold initialized. Use Wails CLI for full desktop runtime.")
}
