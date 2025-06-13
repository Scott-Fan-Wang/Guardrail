import argparse
import asyncio

from sentinelshield.core.orchestrator import build_orchestrator


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run Llama Prompt Guard 2 inference")
    parser.add_argument("text", help="Prompt to evaluate")
    args = parser.parse_args()

    orc = build_orchestrator(model_name="llama_prompt_guard_2")
    resp = await orc.moderate(args.text)
    score = resp.reasons[0].score if resp.reasons else 0.0
    print(f"decision: {resp.decision}, score: {score:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
