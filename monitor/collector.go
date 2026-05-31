package main

import (
	"context"
	"log"
	"runtime"
	"sync"
	"time"
)

// SystemMetrics holds a snapshot of system-level metrics.
type SystemMetrics struct {
	CPUUsage    float64
	AllocMB     float64
	Goroutines  int
	NumGC       uint32
	LastGC      time.Time
}

// Collector periodically collects system metrics and caches them.
type Collector struct {
	mu       sync.RWMutex
	metrics  SystemMetrics
	interval time.Duration
	stopCh   chan struct{}
}

// NewCollector creates a new system metrics collector.
func NewCollector() *Collector {
	return &Collector{
		interval: 15 * time.Second,
		stopCh:   make(chan struct{}),
	}
}

// Start begins periodic metric collection.
func (c *Collector) Start(ctx context.Context) {
	log.Printf("Metrics collector started (interval: %v)", c.interval)

	ticker := time.NewTicker(c.interval)
	defer ticker.Stop()

	// Collect immediately on start
	c.collect()

	for {
		select {
		case <-ticker.C:
			c.collect()
		case <-ctx.Done():
			log.Println("Metrics collector stopped")
			return
		case <-c.stopCh:
			log.Println("Metrics collector stopped via signal")
			return
		}
	}
}

// Stop signals the collector to stop.
func (c *Collector) Stop() {
	close(c.stopCh)
}

// collect gathers a snapshot of system metrics.
func (c *Collector) collect() {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	metrics := SystemMetrics{
		AllocMB:    float64(m.Alloc) / 1024 / 1024,
		Goroutines: runtime.NumGoroutine(),
		NumGC:      m.NumGC,
		LastGC:     time.Unix(0, int64(m.LastGC)),
		// CPU usage: approximate using Go's runtime metrics
		CPUUsage:   0.0, // In production, use gopsutil/cpu
	}

	c.mu.Lock()
	c.metrics = metrics
	c.mu.Unlock()

	log.Printf("Metrics snapshot: Alloc=%.2fMB, Goroutines=%d, GC=%d",
		metrics.AllocMB, metrics.Goroutines, metrics.NumGC)
}

// GetMetrics returns the latest cached metrics snapshot.
func (c *Collector) GetMetrics() SystemMetrics {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.metrics
}