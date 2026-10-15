"""Opt-in paced WAV -> unchanged bridge -> JSON Ollama orchestrator measurement."""
import argparse
import asyncio
import math
import time
import sys

from iot_models.voice_orchestrator import emit, run


async def smoke(args):
    completed = asyncio.Event()
    transcripts = {}
    samples = []
    started = None
    replay = None

    def output(event):
        emit(event)
        if event["type"] == "transcript":
            transcripts[event.get("item_id")] = event.get("text", "")
            if args.expect.lower() in event.get("text", "").lower():
                emit({"type": "stt_measurement", "replay_start_to_final_ms":
                      round((time.monotonic() - started) * 1000, 2)})
        if (event["type"] == "llm_response" and
                args.expect.lower() in transcripts.get(event.get("item_id"), "").lower()):
            emit({"type": "host_pipeline_measurement", "replay_start_to_response_ms":
                  round((time.monotonic() - started) * 1000, 2),
                  "scope": "Paced audio, silence endpoint, STT, queue and LLM; excludes physical device"})
            completed.set()

    async def gpu():
        while True:
            probe = None
            try:
                probe = await asyncio.create_subprocess_exec("nvidia-smi",
                    "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                async with asyncio.timeout(5):
                    raw, _ = await probe.communicate()
                if probe.returncode == 0:
                    samples.append([int(value.strip()) for value in raw.decode().splitlines()[0].split(",")])
            except (OSError, ValueError, TimeoutError):
                return
            finally:
                if probe is not None and probe.returncode is None:
                    probe.kill()
                    await probe.wait()
            await asyncio.sleep(0.5)

    pipeline = asyncio.create_task(run(args, ["--device-ip", "127.0.0.1", "--port", str(args.port)], output))
    monitor = asyncio.create_task(gpu())
    completion = asyncio.create_task(completed.wait())
    try:
        await asyncio.sleep(2)
        if pipeline.done():
            await pipeline
            raise RuntimeError("Pipeline exited before replay")
        started = time.monotonic()
        replay = await asyncio.create_subprocess_exec(sys.executable, "-m", "iot_models.replay_microphone",
                                                      args.wav, "--port", str(args.port))
        done, _ = await asyncio.wait([pipeline, completion], timeout=args.timeout,
                                     return_when=asyncio.FIRST_COMPLETED)
        if pipeline in done:
            await pipeline
            raise RuntimeError("Pipeline exited before reply")
        if not completed.is_set():
            raise RuntimeError("No matching transcript and reply before timeout")
    finally:
        for task in (pipeline, monitor, completion):
            task.cancel()
        await asyncio.gather(pipeline, monitor, completion, return_exceptions=True)
        if replay is not None and replay.returncode is None:
            replay.terminate()
            await replay.wait()
        emit({"type": "gpu_measurement", "samples": len(samples),
              "baseline_used_mib": samples[0][0] if samples else None,
              "peak_used_mib": max(value[0] for value in samples) if samples else None,
              "peak_utilization_percent": max(value[1] for value in samples) if samples else None,
              "scope": "Whole first GPU including other processes; sampled peak is a lower bound"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav")
    parser.add_argument("--expect", default="hello")
    parser.add_argument("--port", type=int, default=15009)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--llm-model", default="qwen3:1.7b")
    parser.add_argument("--llm-timeout", type=float, default=60)
    parser.add_argument("--keep-alive", default="0")
    args = parser.parse_args()
    args.text = None
    if not 1024 <= args.port <= 65535 or not math.isfinite(args.timeout) or not 0 < args.timeout <= 600:
        parser.error("port must be 1024..65535 and timeout must be finite, 0..600 seconds")
    asyncio.run(smoke(args))


if __name__ == "__main__":
    main()
