//go:build wails

package main

import (
	"context"
	"io/fs"
	"os"

	"agenticai/desktop/internal/desktop"
	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	"github.com/wailsapp/wails/v2/pkg/options/windows"
)

func main() {
	app, err := desktop.New("")
	if err != nil {
		panic(err)
	}
	assets := os.DirFS("frontend/dist")
	var normalized fs.FS = assets

	err = wails.Run(&options.App{
		Title:            "Agentic AI Code Review Desktop",
		Width:            1440,
		Height:           900,
		DisableResize:    false,
		Frameless:        false,
		Fullscreen:       false,
		WindowStartState: options.Normal,
		AssetServer: &assetserver.Options{
			Assets: normalized,
		},
		Windows: &windows.Options{
			DisableWindowIcon: false,
		},
		OnStartup: func(ctx context.Context) {},
		OnShutdown: func(ctx context.Context) {
			app.Shutdown()
		},
		Bind: []any{
			app,
		},
	})
	if err != nil {
		panic(err)
	}
}
