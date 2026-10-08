# Benchmark: Phase 2 go/no-go (2026-10-07)

Full-resolution decode + a basic float32 render (exposure, tone curve, saturation, gamma) + JPEG q90 encode in
memory, per photo. Run with `photoedit benchmark` (P2.6) on the 67 Fujifilm X-T3 RAFs (26 MP X-Trans) in
`2026-08-11`. Nothing was written near the photos.

- Machine: i7-12700H (14 cores: 6 performance + 8 efficiency, 20 threads), 16 GB RAM, Windows 11
- Decoder: `dec1-libraw0.22.1-pillow12.3.0`, **LibRaw single-threaded per worker** (its OpenMP decode of X-Trans
  files is not deterministic; see PLAN.md §0), parallelism through worker processes

| Workers | Photos | Total (s) | s / photo | min / 100 photos | Peak RAM |
|---:|---:|---:|---:|---:|---:|
| 1 | 12 | 181.0 | 15.08 | 25.14 | 0.8 GiB |
| 4 | 67 | 278.2 | 4.15 | 6.92 | 2.8 GiB |
| 6 | 67 | 218.7 | 3.26 | 5.44 | 4.1 GiB |
| 8 | 67 | 187.0 | 2.79 | 4.65 | 5.0 GiB |
| 10 | 67 | 168.4 | 2.51 | 4.19 | 6.2 GiB |
| 12 | 67 | 154.7 | 2.31 | 3.85 | 7.6 GiB |
| 14 | 67 | 142.4 | 2.13 | 3.54 | 8.6 GiB |

**GO**: the best configuration (14 workers) takes 3.54 min per 100 photos, under the 5 min limit. 8 workers or more
pass.

## Notes

- Each worker needs about 0.6 GiB. Scaling flattens beyond 8 workers because the extra cores are efficiency cores.
- The sequential baseline (15 s per photo) is about 5× slower than LibRaw's multithreaded decode (~2.5 s). That speed
  isn't available to us, because multithreaded output differs between runs.
- Suggested default for batch export (Phase 5): about 10 workers (4.2 min per 100, 6.2 GiB), which leaves room for the
  browser and other apps on a 16 GB machine. Phase 3/9 can lower the cost further (float16 or tiled processing, GPU).
- Previews are not affected: the half-size decode takes about 1.3 s per photo single-threaded, and is cached.
