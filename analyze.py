import json
import os
from dotenv import load_dotenv
from openai import OpenAI

from schemas import PromptInput, AnalyzerResponse, AnalysisResult
from llm_client import LLMConfig, call_analyzer_llm, LLMCallError
from post_processor import post_process

load_dotenv()



def load_prompt_template() -> str:
    with open("prompts/analyzer_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()


def fallback_analysis(reason: str) -> AnalyzerResponse:
    """
    Guaranteed schema-compliant fallback when LLM fails.
    """
    return AnalyzerResponse(
        input_summary="(fallback)",
        analysis=AnalysisResult(
            risk_level="MEDIUM",
            context_score=0.0,
            detected_issues=["llm_failure"],
            recommendations=[f"LLM analyzer failed: {reason}. Retry later or inspect logs."]
        )
    )


def analyze_prompt(input_data: PromptInput) -> AnalyzerResponse:
    analyzer_prompt = load_prompt_template()

    combined_input = f"""
SYSTEM PROMPT:
{input_data.system_prompt}

USER PROMPT:
{input_data.user_prompt}

CONTEXT:
{input_data.context}
""".strip()

    cfg = LLMConfig()

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY in environment.")

        client = OpenAI(api_key=api_key)

        parsed = call_analyzer_llm(
            client=client,
            cfg=cfg,
            system_prompt=analyzer_prompt,
            user_content=combined_input,
            logger=print,
        )

        analysis = AnalysisResult(**parsed)

        final_risk, final_issues, final_recs, final_context_score = post_process(
            user_prompt=input_data.user_prompt,
            context=input_data.context or "",
            llm_risk_level=analysis.risk_level,
            llm_detected_issues=analysis.detected_issues,
            llm_recommendations=analysis.recommendations,
        )

        final_analysis = AnalysisResult(
            risk_level=final_risk,
            context_score=final_context_score,
            detected_issues=final_issues,
            recommendations=final_recs,
        )

        return AnalyzerResponse(
            input_summary=input_data.user_prompt[:80],
            analysis=final_analysis
        )
        
    except Exception as e:
        return fallback_analysis(str(e))


if __name__ == "__main__":
    with open("examples/day4_case_good.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    input_model = PromptInput(**data)
    result = analyze_prompt(input_model)

    print(result.model_dump_json(indent=2))
