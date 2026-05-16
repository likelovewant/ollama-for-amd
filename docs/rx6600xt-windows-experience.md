# RX 6600 XT (gfx1032) Windows Experience Report

This document captures practical, real-world testing notes for running Ollama on Windows with an AMD RX 6600 XT.

## Scope

- GPU: AMD Radeon RX 6600 XT (gfx1032)
- OS: Windows (PowerShell workflow)
- Runtime target: Ollama + ROCm/HIP backend
- Model target for validation: qwen3.5:9b

## Environment used

- Visual Studio 2022 toolchain environment loaded via vcvarsall (amd64)
- HIP/ROCm path configured to ROCm 6.4
- CGO enabled
- GCC/G++ selected for CC/CXX
- WinLibs/Git/Go/CMake/ROCm binaries added to PATH

Example session setup (used during testing):

```powershell
Set-Location "C:\Users\Rodrigo\source\repos\ollama-for-amd"

$vcvars='C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat'
$tmp=[System.IO.Path]::GetTempFileName()+'.bat'
"@call `"$vcvars`" amd64`nset" | Out-File $tmp -Encoding ASCII
cmd /c $tmp | Where-Object { $_ -match '^[A-Z_]+=.+' } | ForEach-Object {
  $p=$_ -split '=',2
  [System.Environment]::SetEnvironmentVariable($p[0],$p[1],'Process')
}
Remove-Item $tmp -Force

$winlibs='C:\Users\Rodrigo\AppData\Local\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin'
$env:HIP_PATH='C:\Program Files\AMD\ROCm\6.4'
$env:ROCM_PATH='C:\Program Files\AMD\ROCm\6.4'
$env:HIP_PLATFORM='amd'
$env:CGO_ENABLED='1'
$env:CC='gcc'
$env:CXX='g++'
$env:PATH = "$winlibs;C:\Program Files\Git\cmd;C:\Program Files\Go\bin;C:\Program Files\CMake\bin;C:\Program Files\AMD\ROCm\6.4\bin;$env:TEMP\ninja;$env:PATH"
```

## Build result observed

Build command used:

```powershell
.\scripts\build_windows.ps1 ollama
```

Observed result:

- Command completed with exit code 0 in the recorded test session.

## Runtime behavior observed

### Server startup checks

Two startup variants were tested from dist\windows-amd64:

1. With gfx override:

```powershell
$env:OLLAMA_DEBUG='2'
$env:HSA_OVERRIDE_GFX_VERSION='10.3.0'
.\ollama.exe serve
```

2. Without gfx override:

```powershell
$env:OLLAMA_DEBUG='2'
Remove-Item Env:HSA_OVERRIDE_GFX_VERSION -ErrorAction SilentlyContinue
.\ollama.exe serve
```

Observed result in both attempts:

- `ollama serve` exited with code 1.

### Model and CLI checks

Command used:

```powershell
.\ollama.exe pull qwen2.5:0.5b
```

Observed result:

- Pull completed successfully (exit code 0).

Command used:

```powershell
.\ollama.exe list
```

Observed result:

- Command completed successfully (exit code 0), confirming the local model listing path is functional.

### Model residency check (VRAM vs CPU offload)

After loading `qwen3.5:9b` with `keep_alive`, `ollama ps` reported:

- NAME: qwen3.5:9b
- SIZE: 8.8 GB
- PROCESSOR: 28%/72% CPU/GPU
- CONTEXT: 4096

Interpretation:

- In this measured session, the model was not 100% in VRAM.
- Ollama reported partial offload with 72% GPU and 28% CPU.

## qwen3.5:9b validation status

Additional validation was completed successfully after the initial checks.

Commands used:

```powershell
Set-Location "C:\Users\Rodrigo\source\repos\ollama-for-amd\dist\windows-amd64"
.\ollama.exe pull qwen3.5:9b
.\ollama.exe run qwen3.5:9b "Responde exactamente: listo"
```

Observed result:

- Pull completed successfully (exit code 0).
- Direct model run completed successfully (exit code 0).

## Benchmark methodology

Benchmark target:

- Model: qwen3.5:9b
- Prompt: "You are benchmarking. Reply with exactly one short sentence confirming readiness."
- Inference options: `num_predict=128`, `temperature=0`, `seed=123`
- Runs: 1 cold run + 3 warm runs

Metric sources:

- Wall time measured locally in PowerShell (wall_ms)
- Ollama API timings from `/api/generate` (stream=false):
  - total_duration
  - load_duration
  - prompt_eval_duration
  - eval_duration
  - prompt_eval_count
  - eval_count

Derived metrics:

- prompt_tps = prompt_eval_count / (prompt_eval_duration seconds)
- eval_tps = eval_count / (eval_duration seconds)

## Benchmark results

Cold run:

- wall_ms: 28223.45
- total_ms: 28218.93
- load_ms: 22020.85
- prompt_eval_ms: 108.68
- eval_ms: 5813.33
- prompt_eval_count: 24
- eval_count: 128
- prompt_tps: 220.83
- eval_tps: 22.01

Warm runs:

- warm1: wall_ms 6324.44, load_ms 320.96, prompt_tps 231.31, eval_tps 22.05
- warm2: wall_ms 6295.53, load_ms 297.99, prompt_tps 238.90, eval_tps 22.07
- warm3: wall_ms 6315.17, load_ms 300.60, prompt_tps 230.61, eval_tps 21.99

Warm averages:

- avg_wall_ms: 6311.71
- avg_eval_tps: 22.04
- avg_prompt_tps: 233.60

## Current status summary

- Build path: working in tested session
- CLI/model list path: working in tested session
- qwen3.5:9b pull and direct run: working in tested session
- API endpoint was reachable during benchmark execution
- Cold-start penalty is significant (about 22.0s load time in this sample)
- Warm decode throughput for this setup is about 22 tokens/s

## Extended benchmark suite

An additional benchmark pass was executed to collect stability and scaling metrics.

### Stability (20 sequential requests)

Test settings:

- Prompt: "Reply with exactly OK"
- `num_predict=32`, `temperature=0`, `seed=123`, `stream=false`

Results:

- total_runs: 20
- successes: 20
- failures: 0
- success_rate: 100.0%
- p50 latency: 1835.02 ms
- p95 latency: 1862.73 ms

### Output-length sensitivity

Test settings:

- Prompt: "You are benchmarking. Reply with one concise sentence."
- 2 runs per setting
- `num_predict` in: 32, 128, 256, 512

Results (averages):

- num_predict 32: avg_wall_ms 1866.87, avg_eval_tps 22.58
- num_predict 128: avg_wall_ms 6294.59, avg_eval_tps 22.08
- num_predict 256: avg_wall_ms 12233.00, avg_eval_tps 21.98
- num_predict 512: avg_wall_ms 24069.60, avg_eval_tps 21.98

Interpretation:

- End-to-end latency scales almost linearly with output length.
- Decode throughput remains stable at about 22 tok/s across output sizes.

### Context-size sensitivity

Test settings:

- Prompt built by repeating token "bench" to approximate larger contexts
- Context targets: 1k, 4k, 8k tokens
- `num_predict=64`

Results:

- approx_tokens 1000: wall_ms 5140.10, prompt_eval_count 1010, prompt_tps 543.93, eval_tps 21.91
- approx_tokens 4000: wall_ms 9678.93, prompt_eval_count 4010, prompt_tps 626.92, eval_tps 21.92
- approx_tokens 8000: wall_ms 9858.54, prompt_eval_count 4096, prompt_tps 1421.80, eval_tps 9.71

Interpretation:

- In this run, prompt_eval_count was capped at 4096 for the 8k attempt, suggesting an effective context limit in the active configuration.
- Under that 8k-attempt case, generation throughput dropped noticeably versus shorter contexts.

## A/B configuration comparison (for direct comparability)

This section compares two runtime configurations under the same warm-only method.

Method:

- For each config: 1 warm-up request (discarded) + 3 measured requests
- Prompt fixed, `stream=false`, `num_predict=128`, `temperature=0`, `seed=123`, `keep_alive='10m'`

Configurations:

- Config A: default context (no `num_ctx` override)
- Config B: reduced context (`num_ctx=2048`)

Results:

- Config A: PROCESSOR 28%/72% CPU/GPU, CONTEXT 4096, avg_wall_ms 6300.93, avg_load_ms 294.27, avg_eval_tps 22.03, avg_prompt_tps 208.81
- Config B: PROCESSOR 29%/71% CPU/GPU, CONTEXT 2048, avg_wall_ms 6297.03, avg_load_ms 300.88, avg_eval_tps 22.09, avg_prompt_tps 203.55

Delta (B - A):

- wall_ms: -3.89 ms
- eval_tps: +0.06 tok/s
- prompt_tps: -5.25 tok/s

Interpretation:

- In this setup, lowering context from 4096 to 2048 did not materially change warm throughput or latency.
- GPU residency remained practically unchanged (about 71-72% GPU), so this change alone did not move the model to 100% VRAM.

## Full-GPU forcing attempt (same model)

An additional runtime sweep was executed to try to force full GPU residency with the same `qwen3.5:9b` model.

Variants tested:

- V1: default options
- V2: `num_ctx=2048`
- V3: `num_ctx=1024`
- V4: `num_ctx=512`
- V5: `num_ctx=512`, `num_gpu=999`
- V6: `num_ctx=256`, `num_gpu=999`

Observed `ollama ps` processor results:

- V1 to V4: about 28-29% CPU / 71-72% GPU (partial offload)
- V5 and V6: `100% GPU`

Stability check for full-GPU variant:

- Repeated 5 sequential requests with `num_ctx=512`, `num_gpu=999`
- `ollama ps` reported `100% GPU` on all 5 runs

Important note:

- In these runs, `ollama ps` context remained at `2048` even when `num_ctx` was set below that value.
- Practically, the strongest switch for full GPU in this setup was `num_gpu=999`.

## Current confirmed conclusion (no additional runs)

Using only the validated results above:

- Baseline profile remains in partial offload (about 71-72% GPU).
- The same model can be forced to full GPU residency by setting `num_gpu=999`.
- Full-GPU residency was stable across 5 consecutive checks in this session.
- A fresh throughput delta between partial and full-GPU profiles is intentionally not added here, because this revision avoids running new tests.
