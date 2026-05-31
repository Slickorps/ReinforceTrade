package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"runtime"
	"sync"
	"time"
)

// HealthHandler serves the /health endpoint.
type HealthHandler struct {
	startTime time.Time
	mu        sync.RWMutex
	status    string
}

// HealthResponse represents the health check JSON payload.
type HealthResponse struct {
	Status    string `json:"status"`
	Uptime    string `json:"uptime"`
	Version   string `json:"version"`
	GoVersion string `json:"go_version"`
	Timestamp string `json:"timestamp"`
}

// NewHealthHandler creates a new health handler.
func NewHealthHandler() *HealthHandler {
	return &HealthHandler{
		startTime: time.Now(),
		status:    "healthy",
	}
}

// ServeHTTP handles HTTP requests for the health endpoint.
func (h *HealthHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	h.mu.RLock()
	status := h.status
	h.mu.RUnlock()

	uptime := time.Since(h.startTime).Round(time.Second).String()

	resp := HealthResponse{
		Status:    status,
		Uptime:    uptime,
		Version:   "1.0.0",
		GoVersion: runtime.Version(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(resp)
}

// MetricsHandler serves the /metrics endpoint.
type MetricsHandler struct {
	mu sync.RWMutex
}

// MetricsResponse represents system metrics.
type MetricsResponse struct {
	CPU struct {
		UsagePercent float64 `json:"usage_percent"`
		NumCPU       int     `json:"num_cpu"`
	} `json:"cpu"`
	Memory struct {
		AllocMB      float64 `json:"alloc_mb"`
		TotalAllocMB float64 `json:"total_alloc_mb"`
		SysMB        float64 `json:"sys_mb"`
		NumGC        uint32  `json:"num_gc"`
	} `json:"memory"`
	Goroutines int               `json:"goroutines"`
	Timestamp  string            `json:"timestamp"`
	Custom     map[string]float64 `json:"custom,omitempty"`
}

// NewMetricsHandler creates a new metrics handler.
func NewMetricsHandler() *MetricsHandler {
	return &MetricsHandler{}
}

// ServeHTTP handles HTTP requests for the metrics endpoint.
func (h *MetricsHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	resp := MetricsResponse{
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Goroutines: runtime.NumGoroutine(),
	}

	resp.CPU.NumCPU = runtime.NumCPU()
	// Note: In production, use gopsutil/cpu for actual CPU percentage

	resp.Memory.AllocMB = float64(m.Alloc) / 1024 / 1024
	resp.Memory.TotalAllocMB = float64(m.TotalAlloc) / 1024 / 1024
	resp.Memory.SysMB = float64(m.Sys) / 1024 / 1024
	resp.Memory.NumGC = m.NumGC

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(resp)
}

// LatencyHandler serves the /latency endpoint for tracking operation timing.
type LatencyHandler struct {
	mu       sync.RWMutex
	latencies map[string]*LatencyStats
}

// LatencyStats holds statistics for a tracked operation.
type LatencyStats struct {
	Count       int           `json:"count"`
	Min         time.Duration `json:"min"`
	Max         time.Duration `json:"max"`
	Avg         time.Duration `json:"avg"`
	Last        time.Duration `json:"last"`
	Total       time.Duration `json:"total"`
}

// LatencyResponse is the API response for latency data.
type LatencyResponse struct {
	Operations map[string]*LatencyStats `json:"operations"`
	Timestamp  string                   `json:"timestamp"`
}

// NewLatencyHandler creates a new latency handler.
func NewLatencyHandler() *LatencyHandler {
	return &LatencyHandler{
		latencies: make(map[string]*LatencyStats),
	}
}

// RecordLatency records an operation's latency.
func (h *LatencyHandler) RecordLatency(operation string, duration time.Duration) {
	h.mu.Lock()
	defer h.mu.Unlock()

	stats, exists := h.latencies[operation]
	if !exists {
		stats = &LatencyStats{}
		h.latencies[operation] = stats
	}

	stats.Count++
	stats.Last = duration
	stats.Total += duration

	if stats.Count == 1 || duration < stats.Min {
		stats.Min = duration
	}
	if duration > stats.Max {
		stats.Max = duration
	}
	stats.Avg = stats.Total / time.Duration(stats.Count)
}

// ServeHTTP handles HTTP requests for the latency endpoint.
func (h *LatencyHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	resp := LatencyResponse{
		Operations: make(map[string]*LatencyStats),
		Timestamp:  time.Now().UTC().Format(time.RFC3339),
	}

	// Format latencies as milliseconds for JSON output
	for op, stats := range h.latencies {
		formatted := &LatencyStats{
			Count: stats.Count,
			Min:   stats.Min,
			Max:   stats.Max,
			Avg:   stats.Avg,
			Last:  stats.Last,
			Total: stats.Total,
		}
		resp.Operations[op] = formatted
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(resp)
}

// Helper function to convert duration for JSON output
func (l LatencyStats) MarshalJSON() ([]byte, error) {
	return json.Marshal(map[string]interface{}{
		"count": l.Count,
		"min_ms": l.Min.Seconds() * 1000,
		"max_ms": l.Max.Seconds() * 1000,
		"avg_ms": l.Avg.Seconds() * 1000,
		"last_ms": l.Last.Seconds() * 1000,
		"total_ms": l.Total.Seconds() * 1000,
	})
}

// Ensure the string is valid
func (l LatencyStats) String() string {
	return fmt.Sprintf("count=%d, min=%v, max=%v, avg=%v, last=%v",
		l.Count, l.Min, l.Max, l.Avg, l.Last)
}