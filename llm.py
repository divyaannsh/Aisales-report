"""
LLM Natural-Language-to-SQL module for Indus Towers AI Exception Reporter.

Translates natural language business queries into SQLite SELECT queries over
'tower_sites' database using Groq (LLaMA3 / GPT-OSS) or OpenAI API.
"""

import os
import re
from typing import Tuple, List, Optional
from validate import validate_sql

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

FEW_SHOT_EXAMPLES = """
Few-Shot Examples:

Question: Which tower sites in Delhi breached SLA uptime in August 2026?
SQL: SELECT circle, site_id, tenant, colocation_count, target_colocations, uptime_pct, sla_target_pct, energy_consumption_kwh, energy_budget_kwh, month FROM tower_sites WHERE circle = 'Delhi' AND month = '2026-08';

Question: Show Airtel tower sites in Mumbai with colocation shortfall.
SQL: SELECT circle, site_id, tenant, colocation_count, target_colocations, uptime_pct, sla_target_pct, energy_consumption_kwh, energy_budget_kwh, month FROM tower_sites WHERE tenant = 'Airtel' AND circle = 'Mumbai';

Question: List towers in UP-East over budget on energy in July 2026.
SQL: SELECT circle, site_id, tenant, colocation_count, target_colocations, uptime_pct, sla_target_pct, energy_consumption_kwh, energy_budget_kwh, month FROM tower_sites WHERE circle = 'UP-East' AND month = '2026-07';

Question: Show all tower sites for Reliance Jio in Karnataka.
SQL: SELECT circle, site_id, tenant, colocation_count, target_colocations, uptime_pct, sla_target_pct, energy_consumption_kwh, energy_budget_kwh, month FROM tower_sites WHERE tenant = 'Reliance Jio' AND circle = 'Karnataka';
"""


def _get_api_key(key_name: str) -> Optional[str]:
    """Fetch API key from environment variable or Streamlit secrets for production deployment."""
    val = os.environ.get(key_name)
    if val:
        return val

    try:
        import streamlit as st
        if hasattr(st, "secrets") and key_name in st.secrets:
            return st.secrets[key_name]
    except Exception:
        pass

    return None


def _clean_llm_sql_response(raw_response: str) -> str:
    """Extract clean SQL statement from raw LLM text response."""
    clean = raw_response.strip()
    if "```" in clean:
        match = re.search(r"```(?:sql)?\s*(.*?)\s*```", clean, re.DOTALL | re.IGNORECASE)
        if match:
            clean = match.group(1).strip()
    select_match = re.search(r"\b(?:SELECT|WITH)\b.*", clean, re.DOTALL | re.IGNORECASE)
    if select_match:
        clean = select_match.group(0).strip()
    return clean


def _call_llm_api(system_prompt: str, user_prompt: str) -> str:
    """Call Groq or OpenAI API based on credentials."""
    groq_api_key = _get_api_key("GROQ_API_KEY")
    openai_api_key = _get_api_key("OPENAI_API_KEY")

    if groq_api_key:
        from groq import Groq
        client = Groq(api_key=groq_api_key)

        preferred_model = _get_api_key("GROQ_MODEL") or "openai/gpt-oss-120b"
        fallback_models = [preferred_model, "openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile", "llama3-8b-8192"]

        candidate_models = []
        for m in fallback_models:
            if m not in candidate_models:
                candidate_models.append(m)

        for model_name in candidate_models:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.0,
                    max_tokens=300
                )
                return response.choices[0].message.content
            except Exception:
                continue

        raise RuntimeError("All Groq model attempts failed.")

    elif openai_api_key:
        from openai import OpenAI
        client = OpenAI(api_key=openai_api_key)
        model_name = _get_api_key("OPENAI_MODEL") or "gpt-4o-mini"
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=300
        )
        return response.choices[0].message.content

    else:
        return _offline_fallback_sql(user_prompt)


def _offline_fallback_sql(user_prompt: str) -> str:
    """Generate SQL heuristically when running without an API key."""
    prompt_lower = user_prompt.lower()

    circles = ["delhi", "mumbai", "up-east", "up-west", "punjab", "maharashtra", "rajasthan", "karnataka", "tamil nadu", "west bengal"]
    found_circle = None
    for c in circles:
        if c in prompt_lower:
            if c == "up-east": found_circle = "UP-East"
            elif c == "up-west": found_circle = "UP-West"
            elif c == "tamil nadu": found_circle = "Tamil Nadu"
            elif c == "west bengal": found_circle = "West Bengal"
            else: found_circle = c.capitalize()
            break

    tenants = ["airtel", "reliance jio", "jio", "vodafone idea", "vi", "bsnl"]
    found_tenant = None
    for t in tenants:
        if t in prompt_lower:
            if t == "airtel": found_tenant = "Airtel"
            elif t in ["reliance jio", "jio"]: found_tenant = "Reliance Jio"
            elif t in ["vodafone idea", "vi"]: found_tenant = "Vodafone Idea"
            elif t == "bsnl": found_tenant = "BSNL"
            break

    month_map = {
        "march": "2026-03", "april": "2026-04", "may": "2026-05",
        "june": "2026-06", "july": "2026-07", "august": "2026-08"
    }
    found_month = next((m_code for m_name, m_code in month_map.items() if m_name in prompt_lower), None)

    where_clauses = []
    if found_circle:
        where_clauses.append(f"circle = '{found_circle}'")
    if found_tenant:
        where_clauses.append(f"tenant = '{found_tenant}'")
    if found_month:
        where_clauses.append(f"month = '{found_month}'")

    where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    return f"SELECT circle, site_id, tenant, colocation_count, target_colocations, uptime_pct, sla_target_pct, energy_consumption_kwh, energy_budget_kwh, month FROM tower_sites{where_str};"


def nl_to_sql(question: str, schema: str, feedback: Optional[str] = None) -> str:
    """
    Send natural language business question to LLM to produce SQLite SELECT statement for tower_sites.
    """
    system_prompt = (
        "You are an expert SQL engineer. Convert user natural language questions into valid SQLite SELECT queries for 'tower_sites' table.\n"
        "RULES:\n"
        "1. Return ONLY the raw executable SQLite SELECT query. Do not add markdown formatting, markdown backticks, or explanations.\n"
        "2. Do NOT use non-existent table names or column names. Reference ONLY columns and tables present in the schema (table name: tower_sites).\n"
        "3. Always select relevant metrics (circle, site_id, tenant, colocation_count, target_colocations, uptime_pct, sla_target_pct, energy_consumption_kwh, energy_budget_kwh, month).\n"
        "4. Do NOT filter exception thresholds directly in SQL unless explicitly asked — select site metrics rows so the exception layer can evaluate it.\n\n"
        f"Database Schema:\n{schema}\n"
        f"{FEW_SHOT_EXAMPLES}"
    )

    user_prompt = f"Question: {question}"
    if feedback:
        user_prompt += f"\n\nVALIDATION ERROR FROM PREVIOUS ATTEMPT:\n{feedback}\nPlease fix the SQL query to strictly adhere to the schema and rules."

    raw_response = _call_llm_api(system_prompt, user_prompt)
    return _clean_llm_sql_response(raw_response)


def generate_and_validate_sql(
    question: str,
    schema: str,
    allowed_columns: List[str],
    allowed_tables: List[str]
) -> Tuple[bool, str, str, int]:
    """
    Pipeline running NL-to-SQL generation with 2-attempt validation loop.
    """
    sql = nl_to_sql(question, schema)
    is_valid, err_msg = validate_sql(sql, allowed_columns, allowed_tables)

    if is_valid:
        return True, sql, "Validation Passed", 1

    # Attempt 2 Retry
    feedback = f"{err_msg} Please try again."
    sql_retry = nl_to_sql(question, schema, feedback=feedback)
    is_valid_retry, err_msg_retry = validate_sql(sql_retry, allowed_columns, allowed_tables)

    if is_valid_retry:
        return True, sql_retry, "Validation Passed on Attempt 2 (Retry)", 2
    else:
        return False, sql_retry, f"Validation Failed Twice: {err_msg_retry}", 2


def generate_executive_summary(
    question: str,
    flagged_count: int,
    total_count: int,
    exception_type: str,
    top_circles: list,
    avg_uptime: Optional[float],
    energy_overrun_kwh: Optional[float]
) -> str:
    """
    Generate a concise executive-level AI summary of flagged tower exceptions.

    Parameters:
        question: Original natural language question from the user.
        flagged_count: Number of records flagged as exceptions.
        total_count: Total records evaluated.
        exception_type: The exception filter category applied.
        top_circles: List of top circles with most exceptions.
        avg_uptime: Average uptime % of flagged records (None if not applicable).
        energy_overrun_kwh: Total energy variance kWh of flagged records (None if not applicable).

    Returns:
        A 2-3 sentence executive summary string.
    """
    if flagged_count == 0:
        return "✅ No exceptions detected in the queried dataset — all tower sites are operating within defined thresholds."

    uptime_str = f"Average uptime of flagged sites: {avg_uptime:.2f}%." if avg_uptime is not None else ""
    energy_str = f"Total excess energy consumption: {energy_overrun_kwh:,.0f} kWh above budget." if energy_overrun_kwh is not None else ""
    circles_str = f"Most affected circles: {', '.join(top_circles[:3])}." if top_circles else ""

    system_prompt = (
        "You are a senior telecom infrastructure analyst at a tower company (similar to Indus Towers). "
        "Write a concise 2-3 sentence executive summary of an exception report for a business leader. "
        "Be direct, data-driven, and action-oriented. Do not use bullet points. Do not add headers. "
        "Speak like a COO briefing the board. Use ₹ for currency if cost is mentioned."
    )

    user_prompt = (
        f"Original query: '{question}'\n"
        f"Exception category: {exception_type}\n"
        f"Records evaluated: {total_count}\n"
        f"Exceptions flagged: {flagged_count} ({(flagged_count/total_count*100):.1f}% of evaluated records)\n"
        f"{uptime_str}\n"
        f"{energy_str}\n"
        f"{circles_str}\n"
        "Write the executive summary now:"
    )

    try:
        summary = _call_llm_api(system_prompt, user_prompt)
        return summary.strip()
    except Exception:
        # Graceful offline fallback
        pct = (flagged_count / total_count * 100) if total_count > 0 else 0
        parts = [
            f"Out of {total_count} evaluated tower records, {flagged_count} ({pct:.1f}%) were flagged as {exception_type} exceptions."
        ]
        if circles_str:
            parts.append(circles_str)
        if uptime_str:
            parts.append(uptime_str)
        if energy_str:
            parts.append(energy_str)
        parts.append("Immediate review and remediation action is recommended for affected sites.")
        return " ".join(parts)


if __name__ == "__main__":
    from db import get_schema, get_allowed_tables_and_columns

    schema = get_schema()
    tables, cols = get_allowed_tables_and_columns()

    q = "Which tower sites in Delhi breached SLA uptime in August?"
    success, sql, msg, attempts = generate_and_validate_sql(q, schema, cols, tables)
    print(f"Question: {q}\nSuccess: {success}\nSQL: {sql}\nMessage: {msg}\nAttempts: {attempts}")
