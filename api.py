import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from openai import OpenAI

from schemas import PromptInput, AnalyzerResponse, AnalysisResult
from llm_client import LLMConfig, call_analyzer_llm, LLMCallError
from post_processor import post_process

load_dotenv()

app = FastAPI(
    title="ContextGuard API",
    description="LLM Prompt Risk & Context Analyzer",
    version="0.1.0",
)


def load_prompt_template() -> str:
    with open("prompts/analyzer_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()


def fallback_analysis(reason: str) -> AnalyzerResponse:
    return AnalyzerResponse(
        input_summary="(fallback)",
        analysis=AnalysisResult(
            risk_level="MEDIUM",
            context_score=0.0,
            detected_issues=["llm_failure"],
            recommendations=[f"LLM analyzer failed: {reason}. Retry later or inspect logs."]
        )
    )


@app.post("/analyze", response_model=AnalyzerResponse)
def analyze(input_data: PromptInput):
    analyzer_prompt = load_prompt_template()

    combined_input = f"""
SYSTEM PROMPT:
{input_data.system_prompt}

USER PROMPT:
{input_data.user_prompt}

CONTEXT:
{input_data.context}
""".strip()

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY in environment.")

        client = OpenAI(api_key=api_key)
        cfg = LLMConfig()

        parsed = call_analyzer_llm(
            client=client,
            cfg=cfg,
            system_prompt=analyzer_prompt,
            user_content=combined_input,
            logger=print,
        )

        llm_analysis = AnalysisResult(**parsed)

        final_risk, final_issues, final_recs, final_context_score = post_process(
            user_prompt=input_data.user_prompt,
            context=input_data.context or "",
            llm_risk_level=llm_analysis.risk_level,
            llm_detected_issues=llm_analysis.detected_issues,
            llm_recommendations=llm_analysis.recommendations,
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
        # API 層永遠不丟 raw exception 給 client
        return fallback_analysis(str(e))
