package main

import (
	"context"
	"embed"

	"agenticai/desktop/internal/desktop"
	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	"github.com/wailsapp/wails/v2/pkg/options/windows"
)

//go:embed all:frontend/dist
var assets embed.FS

func main() {
	app, err := desktop.New("")
	if err != nil {
		panic(err)
	}

	err = wails.Run(&options.App{
		Title:            "Agentic AI Code Review Desktop",
		Width:            1440,
		Height:           900,
		DisableResize:    false,
		Frameless:        false,
		Fullscreen:       false,
		WindowStartState: options.Normal,
		AssetServer: &assetserver.Options{
			Assets: assets,
		},
		Windows: &windows.Options{
			DisableWindowIcon: false,
		},
		OnStartup: func(ctx context.Context) {},
		Bind: []any{
			app,
		},
	})
	if err != nil {
		panic(err)
	}
}
