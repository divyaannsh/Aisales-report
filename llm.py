"""
LLM Natural-Language-to-SQL module for AI Sales Exception Reporter.

Translates natural language business questions into SQLite SELECT queries
using Groq (LLaMA3 / GPT-OSS) or OpenAI API for Tech Electronics Store dataset.
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

Question: Which cities missed target for iPhone 15 in August 2024?
SQL: SELECT region, product, month, target_units, actual_units FROM sales WHERE product = 'iPhone 15' AND month = '2024-08';

Question: Show sales data for MacBook Air in Mumbai for July 2024.
SQL: SELECT region, product, month, target_units, actual_units FROM sales WHERE product = 'MacBook Air' AND region = 'Mumbai' AND month = '2024-07';

Question: List all product sales in Bengaluru.
SQL: SELECT region, product, month, target_units, actual_units FROM sales WHERE region = 'Bengaluru';

Question: Show performance for Sony Headphones across all cities in June 2024.
SQL: SELECT region, product, month, target_units, actual_units FROM sales WHERE product = 'Sony Headphones' AND month = '2024-06';
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

    products = ["iphone 15", "macbook air", "airpods pro", "samsung s24", "sony headphones"]
    found_product = None
    for p in products:
        if p in prompt_lower:
            if p == "iphone 15": found_product = "iPhone 15"
            elif p == "macbook air": found_product = "MacBook Air"
            elif p == "airpods pro": found_product = "AirPods Pro"
            elif p == "samsung s24": found_product = "Samsung S24"
            elif p == "sony headphones": found_product = "Sony Headphones"
            break

    cities = ["delhi", "mumbai", "bengaluru", "hyderabad"]
    found_city = None
    for c in cities:
        if c in prompt_lower:
            found_city = c.capitalize()
            break

    month_map = {
        "march": "2024-03", "april": "2024-04", "may": "2024-05",
        "june": "2024-06", "july": "2024-07", "august": "2024-08"
    }
    found_month = next((m_code for m_name, m_code in month_map.items() if m_name in prompt_lower), None)

    where_clauses = []
    if found_product:
        where_clauses.append(f"product = '{found_product}'")
    if found_city:
        where_clauses.append(f"region = '{found_city}'")
    if found_month:
        where_clauses.append(f"month = '{found_month}'")

    where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    return f"SELECT region, product, month, target_units, actual_units FROM sales{where_str};"


def nl_to_sql(question: str, schema: str, feedback: Optional[str] = None) -> str:
    """
    Send natural language question to LLM to produce SQLite SELECT query.
    """
    system_prompt = (
        "You are an expert SQL engineer. Convert user natural language questions into valid SQLite SELECT queries.\n"
        "RULES:\n"
        "1. Return ONLY the raw executable SQLite SELECT query. Do not add markdown formatting, markdown backticks, or explanations.\n"
        "2. Do NOT use non-existent table names or column names. Reference ONLY columns and tables present in the schema.\n"
        "3. Always select the relevant columns (region, product, month, target_units, actual_units) so performance can be evaluated.\n"
        "4. Do NOT perform target exception filtering in SQL directly — select target_units and actual_units rows so the exception layer can evaluate it.\n\n"
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


if __name__ == "__main__":
    from db import get_schema, get_allowed_tables_and_columns

    schema = get_schema()
    tables, cols = get_allowed_tables_and_columns()

    q = "Which cities missed target for iPhone 15 in August?"
    success, sql, msg, attempts = generate_and_validate_sql(q, schema, cols, tables)
    print(f"Question: {q}\nSuccess: {success}\nSQL: {sql}\nMessage: {msg}\nAttempts: {attempts}")
