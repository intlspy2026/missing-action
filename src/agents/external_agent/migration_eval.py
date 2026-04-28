"""
Pairwise model migration evaluation for external agent sections.

Compares two model versions side-by-side per case. For each (case, section, metric),
the judge sees both outputs and returns a verdict: A, B, or tie.

Metrics per section:
1. accuracy             (LLM-judge, pairwise) - which output is more grounded in source material?
2. language             (LLM-judge, pairwise) - which output follows language guidelines better?
3. item_count           (deterministic, per-case diff) - directional signal on completeness
4. avg_detail_words     (deterministic, per-case diff) - average words in the detail field per item;
                        read alongside accuracy (high words + flat accuracy = padding)

Expected dataframe columns (one row per case, both models' outputs in same row):
- case_id                      identifier (e.g. "motor_001")
- initial_review               initial review notes (str)
- additional_info              additional info (str)
- doc_request_knowledge        synthesised investigation processes for doc requests (str)
- enquiries_knowledge          synthesised investigation processes for enquiries (str)
- key_concerns_output_a        model A output (JSON str)
- key_concerns_output_b        model B output (JSON str)
- doc_request_output_a / _b    model A / B output (JSON str)
- enquiries_output_a / _b      model A / B output (JSON str)

Usage:
    import pandas as pd
    from agents.external_agent.evals.migration_eval import compare_models

    df = pd.read_excel("eval_paired.xlsx")

    def judge_invoke(prompt: str) -> str:
        # Wrap whatever judge LLM client you have. Must return a string response.
        return judge_llm.invoke(prompt).content

    df_results = compare_models(
        df,
        model_a_name="gpt-4o",
        model_b_name="gpt-5.1",
        judge_invoke_fn=judge_invoke,
    )
    # Aggregates logged to MLflow; per-case verdicts also returned as a dataframe.
"""

import json
import os
import re
import tempfile
from typing import Dict, Any, List, Callable, Tuple

import pandas as pd
import mlflow


# ============================================================
# Section configuration
# ============================================================

SECTIONS: Dict[str, Dict[str, Any]] = {
    "key_concerns": {
        "label": "key concerns",
        "needs_investigation_processes": False,
        "knowledge_col": None,
        "list_field": "concern_set",
        "detail_field": "rationale",
        "source_summary": (
            "Every concern must be traceable to evidence in INITIAL REVIEW or "
            "ADDITIONAL INFORMATION. No fabrication or unsupported inference."
        ),
        "forbidden_terms": [
            "fraudulent", "fraud", "suspicious", "red flags",
            "motive", "collusion", "grossly", "high-risk",
        ],
    },
    "doc_request": {
        "label": "document requests",
        "needs_investigation_processes": True,
        "knowledge_col": "doc_request_knowledge",
        "list_field": "document_set",
        "detail_field": "doc_details",
        "source_summary": (
            "Every doc_type must originate from INVESTIGATION PROCESSES. "
            "INITIAL REVIEW and ADDITIONAL INFORMATION provide case-specific "
            "details for contextualisation - they cannot introduce new doc types."
        ),
        "forbidden_terms": [],
    },
    "enquiries": {
        "label": "additional enquiries",
        "needs_investigation_processes": True,
        "knowledge_col": "enquiries_knowledge",
        "list_field": "enquiries_set",
        "detail_field": "enquiry_detail",
        "source_summary": (
            "Every enquiry topic must originate from INVESTIGATION PROCESSES. "
            "INITIAL REVIEW and ADDITIONAL INFORMATION provide case-specific "
            "details for contextualisation - they cannot introduce new enquiry topics."
        ),
        "forbidden_terms": [],
    },
}


METRICS: Dict[str, Dict[str, str]] = {
    "accuracy": {
        "question": (
            "Which output is more accurate - meaning every item is grounded in "
            "the provided source material with no fabrication or unsupported inference?"
        ),
    },
    "language": {
        "question": (
            "Which output follows language and framing guidelines better - "
            "neutral framing, professional tone, no prohibited terminology, "
            "evidence-framed claims?"
        ),
    },
}


# ============================================================
# Source-material block formatting
# ============================================================

def _format_source_block(row: pd.Series, section_key: str) -> str:
    cfg = SECTIONS[section_key]
    parts: List[str] = []

    if cfg["needs_investigation_processes"]:
        ip = row.get(cfg["knowledge_col"], "") or ""
        parts.extend([
            "<INVESTIGATION PROCESSES>",
            str(ip),
            "</INVESTIGATION PROCESSES>",
            "",
        ])

    parts.extend([
        "<INITIAL REVIEW>",
        str(row.get("initial_review", "")),
        "</INITIAL REVIEW>",
        "",
        "<ADDITIONAL INFORMATION>",
        str(row.get("additional_info", "")),
        "</ADDITIONAL INFORMATION>",
    ])
    return "\n".join(parts)


# ============================================================
# Pairwise judge prompt
# ============================================================

def _build_pairwise_prompt(
    row: pd.Series,
    section_key: str,
    metric_key: str,
    model_a_name: str,
    model_b_name: str,
) -> str:
    cfg = SECTIONS[section_key]
    metric_cfg = METRICS[metric_key]

    output_a = row.get(f"{section_key}_output_a", "") or ""
    output_b = row.get(f"{section_key}_output_b", "") or ""
    source_block = _format_source_block(row, section_key)

    forbidden_block = ""
    if metric_key == "language" and cfg["forbidden_terms"]:
        forbidden_block = (
            f"\nForbidden terminology that must NOT appear in the output: "
            f"{', '.join(cfg['forbidden_terms'])}.\n"
        )

    return f"""You are comparing two model outputs for the '{cfg['label']}' section of an external agent investigation plan.

Source restriction for this section: {cfg['source_summary']}
{forbidden_block}
Question: {metric_cfg['question']}

--- SOURCE MATERIAL ---
{source_block}

--- Output A (model: {model_a_name}) ---
{output_a}

--- Output B (model: {model_b_name}) ---
{output_b}

Compare A and B on the question above. Be specific - cite items in either output that drive your verdict. If neither is meaningfully better, return tie.

Respond in EXACTLY this format on two lines:
Verdict: <A|B|tie>
Justification: <brief explanation citing specific items in A and B>
"""


# ============================================================
# Verdict parsing
# ============================================================

VERDICT_RE = re.compile(r"verdict\s*:\s*(A|B|tie)\b", re.IGNORECASE)
JUSTIFICATION_RE = re.compile(r"justification\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)


def _parse_judge_response(response: str) -> Tuple[str, str]:
    """Parse the judge response into (verdict, justification)."""
    verdict = "tie"
    m = VERDICT_RE.search(response or "")
    if m:
        token = m.group(1)
        if token.upper() == "A":
            verdict = "A"
        elif token.upper() == "B":
            verdict = "B"
        else:
            verdict = "tie"

    j = JUSTIFICATION_RE.search(response or "")
    justification = j.group(1).strip() if j else (response or "").strip()
    return verdict, justification


# ============================================================
# Deterministic item count
# ============================================================

def _count_items(output_str: Any, list_field: str) -> int:
    if not output_str:
        return 0
    try:
        data = json.loads(output_str) if isinstance(output_str, str) else output_str
    except (json.JSONDecodeError, TypeError):
        return 0
    if isinstance(data, dict):
        return len(data.get(list_field) or [])
    return 0


def _avg_detail_words(output_str: Any, list_field: str, detail_field: str) -> float:
    """Average word count of `detail_field` across items in `list_field`."""
    if not output_str:
        return 0.0
    try:
        data = json.loads(output_str) if isinstance(output_str, str) else output_str
    except (json.JSONDecodeError, TypeError):
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    items = data.get(list_field) or []
    if not items:
        return 0.0
    total_words = sum(
        len(str(item.get(detail_field, "") or "").split())
        for item in items if isinstance(item, dict)
    )
    return total_words / len(items)


# ============================================================
# Top-level pairwise comparison
# ============================================================

def compare_models(
    df: pd.DataFrame,
    model_a_name: str,
    model_b_name: str,
    judge_invoke_fn: Callable[[str], str],
) -> pd.DataFrame:
    """
    Run pairwise comparison between two model outputs across 3 sections and 2 LLM-judge metrics.
    Also computes deterministic item-count diffs per section.

    Logs to MLflow:
      - params: model_a, model_b, n_cases
      - metrics per (section, metric): a_win_rate, b_win_rate, tie_rate
      - metrics per section: count_diff_mean, count_a_mean, count_b_mean
      - artifacts: pairwise_results.csv (per-case verdicts), count_diffs.csv

    Returns the per-case verdict dataframe with columns:
        case_id, section, metric, verdict, justification
    """
    verdict_rows: List[Dict[str, Any]] = []
    count_rows: List[Dict[str, Any]] = []

    with mlflow.start_run(run_name=f"{model_a_name}_vs_{model_b_name}"):
        mlflow.log_param("model_a", model_a_name)
        mlflow.log_param("model_b", model_b_name)
        mlflow.log_param("n_cases", len(df))

        for _, row in df.iterrows():
            case_id = row.get("case_id", "unknown")

            # Pairwise judge calls
            for section_key in SECTIONS:
                for metric_key in METRICS:
                    prompt = _build_pairwise_prompt(
                        row, section_key, metric_key, model_a_name, model_b_name
                    )
                    response = judge_invoke_fn(prompt)
                    verdict, justification = _parse_judge_response(response)
                    verdict_rows.append({
                        "case_id": case_id,
                        "section": section_key,
                        "metric": metric_key,
                        "verdict": verdict,
                        "justification": justification,
                    })

            # Deterministic count + avg-detail-words diffs
            for section_key, cfg in SECTIONS.items():
                output_a = row.get(f"{section_key}_output_a")
                output_b = row.get(f"{section_key}_output_b")

                count_a = _count_items(output_a, cfg["list_field"])
                count_b = _count_items(output_b, cfg["list_field"])

                avg_words_a = _avg_detail_words(
                    output_a, cfg["list_field"], cfg["detail_field"]
                )
                avg_words_b = _avg_detail_words(
                    output_b, cfg["list_field"], cfg["detail_field"]
                )

                count_rows.append({
                    "case_id": case_id,
                    "section": section_key,
                    "count_a": count_a,
                    "count_b": count_b,
                    "count_diff_b_minus_a": count_b - count_a,
                    "avg_detail_words_a": avg_words_a,
                    "avg_detail_words_b": avg_words_b,
                    "avg_detail_words_diff_b_minus_a": avg_words_b - avg_words_a,
                })

        df_verdicts = pd.DataFrame(verdict_rows)
        df_counts = pd.DataFrame(count_rows)

        # Aggregate win rates
        for section_key in SECTIONS:
            for metric_key in METRICS:
                subset = df_verdicts[
                    (df_verdicts["section"] == section_key)
                    & (df_verdicts["metric"] == metric_key)
                ]
                total = len(subset) or 1
                a_wins = int((subset["verdict"] == "A").sum())
                b_wins = int((subset["verdict"] == "B").sum())
                ties = int((subset["verdict"] == "tie").sum())

                mlflow.log_metric(f"{section_key}_{metric_key}_a_win_rate", a_wins / total)
                mlflow.log_metric(f"{section_key}_{metric_key}_b_win_rate", b_wins / total)
                mlflow.log_metric(f"{section_key}_{metric_key}_tie_rate", ties / total)

            # Count + avg-detail-words summaries
            section_counts = df_counts[df_counts["section"] == section_key]
            if not section_counts.empty:
                mlflow.log_metric(
                    f"{section_key}_count_a_mean", float(section_counts["count_a"].mean())
                )
                mlflow.log_metric(
                    f"{section_key}_count_b_mean", float(section_counts["count_b"].mean())
                )
                mlflow.log_metric(
                    f"{section_key}_count_diff_mean",
                    float(section_counts["count_diff_b_minus_a"].mean()),
                )
                mlflow.log_metric(
                    f"{section_key}_avg_detail_words_a_mean",
                    float(section_counts["avg_detail_words_a"].mean()),
                )
                mlflow.log_metric(
                    f"{section_key}_avg_detail_words_b_mean",
                    float(section_counts["avg_detail_words_b"].mean()),
                )
                mlflow.log_metric(
                    f"{section_key}_avg_detail_words_diff_mean",
                    float(section_counts["avg_detail_words_diff_b_minus_a"].mean()),
                )

        # Artifacts: per-case rows for drill-in analysis
        with tempfile.TemporaryDirectory() as tmp:
            verdicts_path = os.path.join(tmp, "pairwise_results.csv")
            counts_path = os.path.join(tmp, "count_diffs.csv")
            df_verdicts.to_csv(verdicts_path, index=False)
            df_counts.to_csv(counts_path, index=False)
            mlflow.log_artifact(verdicts_path)
            mlflow.log_artifact(counts_path)

    return df_verdicts
