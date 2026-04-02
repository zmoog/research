package main

import (
	"log"

	"go.opentelemetry.io/collector/component"
	"go.opentelemetry.io/collector/confmap"
	"go.opentelemetry.io/collector/confmap/provider/envprovider"
	"go.opentelemetry.io/collector/confmap/provider/fileprovider"
	"go.opentelemetry.io/collector/otelcol"
)

func main() {
	info := component.BuildInfo{
		Command:     "ecf-aca-collector",
		Description: "EDOT Cloud Forwarder for Azure (ACA)",
		Version:     "0.1.0",
	}

	settings := otelcol.CollectorSettings{
		BuildInfo: info,
		Factories: components,
		ConfigProviderSettings: otelcol.ConfigProviderSettings{
			ResolverSettings: confmap.ResolverSettings{
				ProviderFactories: []confmap.ProviderFactory{
					envprovider.NewFactory(),
					fileprovider.NewFactory(),
				},
				ConverterFactories: []confmap.ConverterFactory{},
			},
		},
	}

	cmd := otelcol.NewCommand(settings)
	if err := cmd.Execute(); err != nil {
		log.Fatalf("collector failed: %v", err)
	}
}
