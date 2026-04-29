import os
import json
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from tavily import TavilyClient

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

MODEL = "llama-3.3-70b-versatile"

with open("faq_data.json", "r") as f:
    FAQ_DATA = json.load(f)

GREETINGS = {
    "hi", "hello", "hey", "hii", "helo", "sup", "yo",
    "hiya", "greetings", "good morning", "good evening", "good afternoon"
}

# ── NEW FLOW ──
# 1. Web search FIRST (real-time JECRC site data)
# 2. If web finds nothing → local FAQ
# 3. If FAQ also nothing → log for staff
SYSTEM_PROMPT = """You are a student support assistant for JECRC University, Jaipur.

You have access to these tools:
- search_jecrc_website: Search JECRC website and web in real time (ALWAYS USE THIS FIRST)
- search_faq: Search local JECRC FAQ database (only if web search returns NOT_FOUND)
- log_unanswered_query: Log query for staff if BOTH tools failed
- answer: Give final answer to student

STRICT ORDER:
1. ALWAYS call search_jecrc_website FIRST for any question
2. If web search gives useful info -> call answer immediately
3. If web returns NOT_FOUND -> call search_faq
4. If FAQ also returns NOT_FOUND -> call log_unanswered_query then call answer
5. Never call the same tool twice
6. Never log if you found useful info

Respond ONLY with valid JSON:
{"tool": "tool_name_here", "query": "input for tool OR final answer text"}

No explanation. No markdown. Just JSON."""


def search_faq(query: str) -> str:
    words = [w.lower() for w in query.split() if len(w) >= 2]
    if not words:
        return "NOT_FOUND"
    scored = []
    for item in FAQ_DATA:
        score = sum(
            3 if w in item["question"].lower() else
            1 if w in item["answer"].lower() else 0
            for w in words
        )
        if score > 0:
            scored.append((score, item))
    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        return "\n\n".join(i["answer"] for _, i in scored[:2])
    return "NOT_FOUND"


def search_jecrc_website(query: str) -> str:
    try:
        r = tavily_client.search(
            query=f"JECRC University Jaipur {query}",
            search_depth="basic",
            include_domains=["jecrcuniversity.edu.in", "jecrc.com"],
            max_results=5
        )
        results = r.get("results", [])
        combined = "\n\n".join(
            f"{x.get('title','')}: {x.get('content','')}"
            for x in results if x.get("content")
        )
        if len(combined) > 100:
            return combined[:3000]

        r2 = tavily_client.search(
            query=f"JECRC University Jaipur {query}",
            search_depth="basic",
            max_results=5
        )
        results2 = r2.get("results", [])
        combined2 = "\n\n".join(
            f"{x.get('title','')}: {x.get('content','')}"
            for x in results2 if x.get("content")
        )
        if len(combined2) > 100:
            return combined2[:3000]

        return "NOT_FOUND"

    except Exception as e:
        print(f"[Tavily Error]: {e}")
        return "NOT_FOUND"


def log_unanswered_query(query: str) -> str:
    try:
        with open("unanswered_log.txt", "a") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {query}\n")
        return "LOGGED"
    except Exception:
        return "LOGGED"


def call_llm(messages: list) -> dict:
    response = groq_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=300
    )
    raw = response.choices[0].message.content.strip()
    print(f"[LLM] {raw[:120]}")
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def is_statement(text: str) -> bool:
    text = text.strip().lower()
    if len(text.split()) < 3:
        return True
    starters = ["it also", "it has", "they also", "okay", "ok", "got it",
                 "thanks", "thank you", "nice", "cool", "great", "i see",
                 "yes", "no", "alright", "that's", "interesting"]
    if any(text.startswith(s) for s in starters):
        return True
    question_words = ["what", "how", "when", "where", "who", "which", "can",
                      "is", "are", "do", "does", "will", "should", "tell",
                      "explain", "give", "help", "show"]
    return not any(text.startswith(w) for w in question_words) and "?" not in text


def get_agent_response(query: str):
    if query.strip().lower() in GREETINGS:
        return (
            "Hello! 👋 Welcome to JECRC Student Support. "
            "Ask me anything about fees, hostel, exams, attendance, placements, or any university procedure.",
            []
        )
    if is_statement(query):
        return (
            "Thanks for sharing! Do you have a specific question about JECRC University? "
            "I can help with fees, hostel, exams, attendance, placements and more. 😊",
            []
        )

    steps = []
    tools_used = set()
    found_useful = False

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Student question: {query}"}
    ]

    try:
        for iteration in range(6):
            decision = call_llm(messages)
            tool = decision.get("tool", "answer")
            tool_input = decision.get("query", "")

            print(f"[Agent {iteration+1}] {tool} | {tool_input[:60]}")

            if tool == "answer":
                return (tool_input.strip(), steps)

            if tool in tools_used:
                messages.append({"role": "user",
                    "content": "Already used that tool. Call 'answer' with your best response now."})
                continue

            tools_used.add(tool)

            if tool == "log_unanswered_query" and found_useful:
                messages.append({"role": "user",
                    "content": "Question already answered. Call 'answer' with final response."})
                continue

            if tool == "search_jecrc_website":
                result = search_jecrc_website(tool_input)
                steps.append(("search_jecrc_website", tool_input))
            elif tool == "search_faq":
                result = search_faq(tool_input)
                steps.append(("search_faq", tool_input))
            elif tool == "log_unanswered_query":
                result = log_unanswered_query(tool_input)
                steps.append(("log_unanswered_query", tool_input))
            else:
                result = "Unknown tool."

            if result not in ["NOT_FOUND", "LOGGED"] and len(result) > 30:
                found_useful = True

            print(f"[Result] {result[:100]}")
            messages.append({"role": "user",
                "content": f"Tool '{tool}' returned: {result}\n\nDecide next action as JSON."})

        messages.append({"role": "user",
            "content": "Give final answer as JSON with tool 'answer'."})
        final = call_llm(messages)
        return (final.get("query", "Please visit jecrcuniversity.edu.in or the admin office.").strip(), steps)

    except json.JSONDecodeError:
        print("[JSON fallback]")
        try:
            simple = groq_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for JECRC University Jaipur. Answer in 3-4 sentences specifically."},
                    {"role": "user", "content": query}
                ],
                temperature=0.3, max_tokens=300
            )
            return (simple.choices[0].message.content.strip(), steps)
        except Exception:
            return ("Please visit jecrcuniversity.edu.in or the JECRC admin office.", steps)

    except Exception as e:
        print(f"[ERROR]: {e}")
        return (f"Technical issue: {str(e)[:120]}", steps)