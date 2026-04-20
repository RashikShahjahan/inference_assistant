from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATASET_CACHE_DIR = ROOT / ".cache" / "huggingface"
CONFIG_PATH = ROOT / "config.json"
GENERATE_PATH = ROOT / "generate.py"
RESULTS_PATH = ROOT / "results.tsv"
STATE_DIR = ROOT / "state"
INCUMBENT_PATH = STATE_DIR / "best_generate.py"


@dataclass(frozen=True)
class Config:
    model: str
    source_lang: str
    target_lang: str
    dataset_repo: str
    dataset_file: str
    dataset_source_field: str
    dataset_reference_field: str
    dataset_fixture_limit: int | None
    dataset_skip_bad_source: bool
    max_new_tokens: int
    max_peak_metal_mb: float | None


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    source_text: str
    reference_text: str
    max_tokens: int | None = None


def load_config() -> Config:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    max_peak_metal_mb = payload.get("max_peak_metal_mb")
    if max_peak_metal_mb is not None:
        max_peak_metal_mb = float(max_peak_metal_mb)
    dataset_source_field = str(payload["dataset_source_field"])
    dataset_reference_field = payload.get("dataset_reference_field")
    if dataset_reference_field is None:
        if dataset_source_field == "source":
            dataset_reference_field = "target"
        elif dataset_source_field == "target":
            dataset_reference_field = "source"
        else:
            raise ValueError(
                "config.json must set dataset_reference_field when dataset_source_field is not 'source' or 'target'"
            )
    return Config(
        model=str(payload["model"]),
        source_lang=str(payload["source_lang"]),
        target_lang=str(payload["target_lang"]),
        dataset_repo=str(payload["dataset_repo"]),
        dataset_file=str(payload["dataset_file"]),
        dataset_source_field=dataset_source_field,
        dataset_reference_field=str(dataset_reference_field),
        dataset_fixture_limit=(
            int(payload["dataset_fixture_limit"])
            if payload.get("dataset_fixture_limit") is not None
            else None
        ),
        dataset_skip_bad_source=bool(payload["dataset_skip_bad_source"]),
        max_new_tokens=int(payload["max_new_tokens"]),
        max_peak_metal_mb=max_peak_metal_mb,
    )


def require_memory_limit(config: Config) -> None:
    if config.max_peak_metal_mb is None or config.max_peak_metal_mb <= 0:
        raise ValueError("config.json must set max_peak_metal_mb to a positive value")


def dataset_fixture_id(payload: dict, line_number: int) -> str:
    lp = str(payload.get("lp") or "row")
    segment_id = payload.get("segment_id")
    if segment_id is None:
        return f"{lp}-{line_number:04d}"
    return f"{lp}-{int(segment_id):04d}"


def load_fixtures() -> list[Fixture]:
    from huggingface_hub import hf_hub_download

    config = load_config()
    dataset_path = Path(
        hf_hub_download(
            repo_id=config.dataset_repo,
            filename=config.dataset_file,
            repo_type="dataset",
            cache_dir=DATASET_CACHE_DIR,
        )
    )
    fixtures: list[Fixture] = []
    seen_ids: set[str] = set()
    for line_number, raw_line in enumerate(
        dataset_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if config.dataset_skip_bad_source and payload.get("is_bad_source"):
            continue
        source_text = str(payload.get(config.dataset_source_field, "")).strip()
        reference_text = str(payload.get(config.dataset_reference_field, "")).strip()
        if not source_text or not reference_text:
            continue
        fixture_id = dataset_fixture_id(payload, line_number)
        if fixture_id in seen_ids:
            raise ValueError(
                f"Duplicate fixture id at line {line_number}: {fixture_id}"
            )
        seen_ids.add(fixture_id)
        fixtures.append(
            Fixture(
                fixture_id=fixture_id,
                source_text=source_text,
                reference_text=reference_text,
            )
        )
        if (
            config.dataset_fixture_limit is not None
            and len(fixtures) >= config.dataset_fixture_limit
        ):
            break
    if not fixtures:
        raise ValueError(
            f"No usable fixtures found in {config.dataset_repo}/{config.dataset_file}"
        )
    return fixtures


def load_model_and_tokenizer(config: Config):
    from mlx_lm import load

    model, tokenizer = load(config.model)
    tokenizer.add_eos_token("<end_of_turn>")
    return model, tokenizer


def build_prompt(tokenizer, config: Config, source_text: str):
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "source_lang_code": config.source_lang,
                    "target_lang_code": config.target_lang,
                    "text": source_text.strip(),
                }
            ],
        }
    ]
    return tokenizer.apply_chat_template(messages, add_generation_prompt=True)


def max_tokens_for_fixture(config: Config, fixture: Fixture) -> int:
    return (
        fixture.max_tokens if fixture.max_tokens is not None else config.max_new_tokens
    )


def ensure_results_header():
    if RESULTS_PATH.exists():
        return
    RESULTS_PATH.write_text(
        "run_id\tmode\tcandidate_hash\tincumbent_hash\tcandidate_tps\tincumbent_tps\tpeak_metal_mb\tstatus\tdescription\n",
        encoding="utf-8",
    )
def promote_candidate():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(GENERATE_PATH, INCUMBENT_PATH)


def main() -> int:
    config = load_config()
    require_memory_limit(config)
    load_fixtures()
    promote_candidate()
    ensure_results_header()
    print(
        json.dumps(
            {
                "status": "initialized",
                "incumbent": str(INCUMBENT_PATH),
                "results": str(RESULTS_PATH),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
