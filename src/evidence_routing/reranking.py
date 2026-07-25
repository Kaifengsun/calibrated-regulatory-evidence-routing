"""Frozen reranking contract and lazy Qwen3 implementation."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from evidence_routing.adapters.base import RetrievalCandidate


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: RetrievalCandidate
    reranker_score: float | None


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
    ) -> tuple[ScoredCandidate, ...]: ...


def direct_candidates(
    candidates: Sequence[RetrievalCandidate],
) -> tuple[ScoredCandidate, ...]:
    return tuple(ScoredCandidate(candidate=row, reranker_score=None) for row in candidates)


def rank_with_scores(
    candidates: Sequence[RetrievalCandidate],
    scores: Sequence[float],
) -> tuple[ScoredCandidate, ...]:
    """Validate and rank one score per candidate under the frozen tie-break."""
    if len(candidates) != len(scores):
        raise ValueError(
            f"reranker score count mismatch: candidates={len(candidates)} scores={len(scores)}"
        )
    source_ids = [row.section.source_id for row in candidates]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("reranker candidates contain duplicate source IDs")
    normalized: list[ScoredCandidate] = []
    for candidate, raw_score in zip(candidates, scores, strict=True):
        score = float(raw_score)
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(f"reranker score must be finite and in [0, 1]: {raw_score!r}")
        normalized.append(ScoredCandidate(candidate=candidate, reranker_score=score))
    return tuple(
        sorted(
            normalized,
            key=lambda row: (
                -float(row.reranker_score),
                row.candidate.rank,
                row.candidate.section.source_id,
            ),
        )
    )


def model_manifest_sha256(snapshot_path: Path) -> str:
    """Reproduce the frozen canonical file-manifest hash."""
    root = snapshot_path.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"reranker snapshot does not exist: {snapshot_path}")
    manifest: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        manifest.append(
            {
                "name": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": digest.hexdigest(),
            }
        )
    canonical = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class QwenFrozenReranker:
    """Lazy local-only scorer for the frozen Qwen3-Reranker snapshot."""

    def __init__(
        self,
        snapshot_path: Path,
        *,
        config_path: Path,
        device: str = "cuda:0",
        verify_manifest: bool = True,
    ) -> None:
        self.snapshot_path = snapshot_path.resolve()
        self.config_path = config_path.resolve()
        payload = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != "1.0":
            raise ValueError("invalid reranker configuration")
        self.config = payload
        self.device = device
        if verify_manifest:
            actual = model_manifest_sha256(self.snapshot_path)
            expected = str(payload["model"]["snapshot_manifest_sha256"])
            if actual != expected:
                raise ValueError(
                    f"reranker snapshot manifest mismatch: expected={expected} actual={actual}"
                )
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._false_token_id: int | None = None
        self._true_token_id: int | None = None
        self._prefix_tokens: list[int] | None = None
        self._suffix_tokens: list[int] | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as error:
            raise RuntimeError(
                "Qwen reranking requires the local torch and transformers runtime"
            ) from error
        inference = self.config["inference"]
        text_processor = AutoTokenizer.from_pretrained(
            self.snapshot_path,
            local_files_only=True,
            padding_side=str(inference["padding_side"]),
        )
        text_processor.pad_token = text_processor.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            self.snapshot_path,
            local_files_only=True,
            dtype=torch.bfloat16,
        ).to(self.device)
        model.eval()
        torch.manual_seed(int(inference["seed"]))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(inference["seed"]))
        torch.use_deterministic_algorithms(bool(inference["deterministic_algorithms"]))

        no_label_id = text_processor.convert_tokens_to_ids(
            str(inference["false_token"])
        )
        yes_label_id = text_processor.convert_tokens_to_ids(
            str(inference["true_token"])
        )
        if (
            no_label_id == text_processor.unk_token_id
            or yes_label_id == text_processor.unk_token_id
        ):
            raise RuntimeError("Qwen3 yes/no scoring tokens are unavailable")
        prefix = (
            f"<|im_start|>system\n{self.config['inference']['system_prompt']}"
            "<|im_end|>\n<|im_start|>user\n"
        )
        suffix = (
            "<|im_end|>\n<|im_start|>assistant\n"
            f"{self.config['inference']['assistant_prefix']}\n\n"
        )
        self._torch = torch
        self._tokenizer = text_processor
        self._model = model
        self._false_token_id = int(no_label_id)
        self._true_token_id = int(yes_label_id)
        self._prefix_tokens = text_processor.encode(prefix, add_special_tokens=False)
        self._suffix_tokens = text_processor.encode(suffix, add_special_tokens=False)

    def _documents(
        self, candidates: Sequence[RetrievalCandidate]
    ) -> list[str]:
        maximum = int(
            max(
                self.config["payload"]["chemical"]["maximum_content_characters"],
                self.config["payload"]["pharmaceutical"]["maximum_content_characters"],
            )
        )
        documents: list[str] = []
        for candidate in candidates:
            section = candidate.section
            text = section.reranker_text or "\n".join(
                value for value in (section.heading, section.content) if value
            )
            documents.append(unicodedata.normalize("NFC", text)[:maximum])
        return documents

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
    ) -> tuple[ScoredCandidate, ...]:
        if not candidates:
            return ()
        self._ensure_loaded()
        text_processor = self._tokenizer
        model = self._model
        torch = self._torch
        assert self._prefix_tokens is not None
        assert self._suffix_tokens is not None
        maximum_length = int(self.config["inference"]["maximum_input_tokens"])
        content_maximum = (
            maximum_length - len(self._prefix_tokens) - len(self._suffix_tokens)
        )
        if content_maximum <= 0:
            raise RuntimeError("maximum input length cannot contain the frozen prompt")
        instruction = str(self.config["inference"]["task_instruction"])
        template = str(self.config["inference"]["user_format"])
        normalized_query = unicodedata.normalize("NFC", query)
        formatted = [
            template.format(
                task_instruction=instruction,
                query=normalized_query,
                document=document,
            )
            for document in self._documents(candidates)
        ]
        scores: list[float] = []
        batch_size = int(self.config["inference"]["batch_size"])
        for offset in range(0, len(formatted), batch_size):
            batch = formatted[offset : offset + batch_size]
            encoded = text_processor(
                batch,
                padding=False,
                truncation=True,
                max_length=content_maximum,
                add_special_tokens=False,
            )
            model_inputs = [
                {
                    "input_ids": self._prefix_tokens + token_ids + self._suffix_tokens,
                    "attention_mask": [1]
                    * (
                        len(self._prefix_tokens)
                        + len(token_ids)
                        + len(self._suffix_tokens)
                    ),
                }
                for token_ids in encoded["input_ids"]
            ]
            inputs = text_processor.pad(
                model_inputs,
                padding=True,
                return_tensors="pt",
            ).to(model.device)
            with torch.inference_mode():
                hidden = model.model(
                    **inputs,
                    return_dict=True,
                ).last_hidden_state[:, -1, :]
                logits = model.get_output_embeddings()(hidden).float()
                binary_logits = torch.stack(
                    [
                        logits[:, self._false_token_id],
                        logits[:, self._true_token_id],
                    ],
                    dim=1,
                )
                scores.extend(torch.softmax(binary_logits, dim=1)[:, 1].cpu().tolist())
        return rank_with_scores(candidates, scores)
