// ReinforceTrade Monitoring Agent
//
// A lightweight system monitoring agent that exposes health, metrics,
// and latency endpoints for the trading system.
//
// Endpoints:
//   GET /health    - Health check
//   GET /metrics   - Prometheus metrics (CPU, memory, goroutines)
//   GET /latency   - Backtest/trading latency tracking

package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

const (
	defaultPort = ":9090"
	shutdownTimeout = 10 * time.Second
)

func main() {
	port := os.Getenv("MONITOR_PORT")
	if port == "" {
		port = defaultPort
	}

	mux := http.NewServeMux()

	// Initialize components
	healthHandler := NewHealthHandler()
	metricsHandler := NewMetricsHandler()
	latencyHandler := NewLatencyHandler()

	// Register routes
	mux.HandleFunc("/health", healthHandler.ServeHTTP)
	mux.HandleFunc("/metrics", metricsHandler.ServeHTTP)
	mux.HandleFunc("/latency", latencyHandler.ServeHTTP)

	// Create server
	server := &http.Server{
		Addr:         port,
		Handler:      loggingMiddleware(mux),
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start metrics collection
	collector := NewCollector()
	go collector.Start(context.Background())

	// Graceful shutdown
	go func() {
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
		<-sigChan

		log.Println("Shutting down monitoring agent...")
		ctx, cancel := context.WithTimeout(context.Background(), shutdownTimeout)
		defer cancel()

		collector.Stop()
		if err := server.Shutdown(ctx); err != nil {
			log.Fatalf("Server forced shutdown: %v", err)
		}
	}()

	log.Printf("ReinforceTrade Monitoring Agent starting on %s", port)
	log.Printf("  Health: http://localhost%s/health", port)
	log.Printf("  Metrics: http://localhost%s/metrics", port)
	log.Printf("  Latency: http://localhost%s/latency", port)

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server failed: %v", err)
	}

	log.Println("Server stopped gracefully")
}

// loggingMiddleware wraps an HTTP handler with request logging.
func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		log.Printf("[%s] %s %s", r.Method, r.URL.Path, r.RemoteAddr)
		next.ServeHTTP(w, r)
		log.Printf("[%s] %s completed in %v", r.Method, r.URL.Path, time.Since(start))
	})
}