"""
reasoning_engine.py  –  AI Recommendation Module
Uses LangChain + Groq to generate structured financial insights.
(Chapter 4.3 – AI Recommendation Module, Chapter 4.4 – Algorithm 5)
"""

import time

try:
    from langchain_groq import ChatGroq
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    from pydantic import BaseModel, conint
    AI_IMPORT_ERROR = None
except ImportError as exc:
    ChatGroq = None
    PromptTemplate = None
    PydanticOutputParser = None
    BaseModel = object
    conint = int
    AI_IMPORT_ERROR = exc

from config import get_settings, require_groq_config

CLOUD_MODEL_NAME = get_settings().cloud_model_name

llm = None   # Lazy-initialised singleton


# ==============================
# OUTPUT SCHEMA
# ==============================

if AI_IMPORT_ERROR is None:
    class FinancialInsight(BaseModel):
        summary:                str
        key_risk:               str
        recommendation:         str
        urgent_action_required: bool
        confidence_score:       conint(ge=50, le=95)

    parser = PydanticOutputParser(pydantic_object=FinancialInsight)
else:
    FinancialInsight = None
    parser = None



# ==============================
# PROMPT TEMPLATE
# ==============================

if AI_IMPORT_ERROR is None:
    financial_prompt = PromptTemplate(
        template="""
You are a professional CFO advisor for Indian SMEs and startups.

Financial Snapshot:
Revenue:        ₹ {revenue}
Expenses:       ₹ {expenses}
Profit Margin:  {profit_margin}%
Cash Runway:    {cash_runway_days} days
Risk Level:     {risk_level}
Revenue Trend:  {revenue_trend_percent}%

CRITICAL RULES:
- Base all reasoning strictly on the provided numbers.
- Do NOT give generic advice.
- Avoid unrealistic cost cuts or growth promises.
- Recommend realistic 5–10% optimisations only.
- Focus on liquidity stabilisation.
- urgent_action_required MUST be true if:
      • cash runway < 60 days
      OR
      • risk level = High

CONFIDENCE SCORE GUIDE:
90–95 → Directly addresses core risk, highly feasible
75–89 → Strong but execution-dependent
60–74 → Moderate impact
50–59 → Limited impact
(Round to nearest multiple of 5.)

Return ONLY valid JSON. No preamble, no markdown fences.

{format_instructions}
""",
        input_variables=[
            "revenue",
            "expenses",
            "profit_margin",
            "cash_runway_days",
            "risk_level",
            "revenue_trend_percent"
        ],
        partial_variables={
            "format_instructions": parser.get_format_instructions()
        }
    )
else:
    financial_prompt = None


# ==============================
# CHAIN FACTORY
# ==============================

def get_chain():
    global llm
    if AI_IMPORT_ERROR is not None:
        raise RuntimeError(
            "AI dependencies are not installed. Run 'python -m pip install -r requirements.txt'."
        ) from AI_IMPORT_ERROR
    if llm is None:
        require_groq_config()
        llm = ChatGroq(model=CLOUD_MODEL_NAME, temperature=0)
    return financial_prompt | llm | parser


# ==============================
# BUSINESS RULE ENFORCEMENT
# ==============================

def enforce_urgent_logic(summary_data: dict, structured_output: dict) -> dict:
    """
    Overrides model output if business rules mandate urgent action.
    Prevents false negatives from the LLM.
    """
    runway = summary_data.get("cash_runway_days")
    if (runway is not None and runway < 60) or summary_data.get("risk_level") == "High":
        structured_output["urgent_action_required"] = True
    return structured_output


# ==============================
# MAIN ENTRY POINT
# ==============================

def generate_financial_insight(summary_data: dict, execution_path: str) -> dict:
    """
    Algorithm 5 (Section 4.4):
    Calls Groq-hosted LLM via LangChain to generate structured
    financial recommendations.

    Args:
        summary_data:   Output of generate_financial_summary()
        execution_path: Must be "amd_cloud" for cloud inference

    Returns:
        dict with keys: analysis, execution_path, model_used,
                        inference_time, success, [error]
    """
    if execution_path.lower() != "amd_cloud":
        raise ValueError(
            "reasoning_engine should only be called with execution_path='amd_cloud'"
        )

    start = time.time()

    try:
        chain           = get_chain()
        result          = chain.invoke(summary_data)
        structured_out  = result.model_dump()
        structured_out  = enforce_urgent_logic(summary_data, structured_out)
        success         = True
    except Exception as e:
        return {
            "analysis":        None,
            "execution_path":  execution_path,
            "model_used":      CLOUD_MODEL_NAME,
            "inference_time":  None,
            "success":         False,
            "error":           str(e)
        }

    return {
        "analysis":        structured_out,
        "execution_path":  execution_path,
        "model_used":      CLOUD_MODEL_NAME,
        "execution_type":  "cloud_groq",
        "inference_time":  round(time.time() - start, 3),
        "success":         success
    }
