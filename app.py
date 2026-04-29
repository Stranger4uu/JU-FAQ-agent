import streamlit as st
import os
import time

st.set_page_config(
    page_title="JECRC Student Support",
    page_icon="🎓",
    layout="centered"
)

# ── Header ──
st.title("🎓 JECRC Student Support Agent")
st.markdown("Powered by **Agentic AI** — searches FAQ + JECRC website in real time")

# ── Demo quick-fire buttons (for meeting demo) ──
st.markdown("**💡 Try asking:**")
demo_questions = [
    "What is the fee for B.Tech CSE?",
    "What is the minimum attendance required?",
    "How do I apply for a scholarship?",
    "What are the hostel fee details?",
    "How do I register for placements?",
    "How do I get a bonafide certificate?",
]
cols = st.columns(2)
for i, q in enumerate(demo_questions):
    if cols[i % 2].button(q, key=f"demo_{i}"):
        st.session_state["prefill"] = q
        st.rerun()

st.divider()

# ── Chat history ──
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("steps"):
            with st.expander("🔍 See how the agent found this"):
                for tool_name, tool_input in msg["steps"]:
                    if tool_name == "search_faq":
                        st.markdown(f"📚 **Searched local FAQ database** → `{tool_input}`")
                    elif tool_name == "search_jecrc_website":
                        st.markdown(f"🌐 **Searched JECRC website** → `{tool_input}`")
                    elif tool_name == "log_unanswered_query":
                        st.markdown(f"📝 **Logged for staff review** → `{tool_input}`")


def handle_query(user_input: str):
    """Process a query and update chat."""
    st.session_state.messages.append({
        "role": "user", "content": user_input, "steps": []
    })
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        status = st.status("Agent is working...", expanded=True)
        with status:
            st.write("🧠 Understanding your question...")
            from agent import get_agent_response
            response, steps = get_agent_response(user_input)

            for tool_name, tool_input in steps:
                if tool_name == "search_faq":
                    st.write("📚 Searching local FAQ database...")
                elif tool_name == "search_jecrc_website":
                    st.write(f"🌐 Searching JECRC website for: *{tool_input}*")
                elif tool_name == "log_unanswered_query":
                    st.write("📝 Logging query for staff review...")
                time.sleep(0.15)

            st.write("✅ Answer ready!")

        status.update(label="Done", state="complete", expanded=False)
        st.write(response)

        if steps:
            with st.expander("🔍 See how the agent found this"):
                for tool_name, tool_input in steps:
                    if tool_name == "search_faq":
                        st.markdown(f"📚 **Searched local FAQ database** → `{tool_input}`")
                    elif tool_name == "search_jecrc_website":
                        st.markdown(f"🌐 **Searched JECRC website** → `{tool_input}`")
                    elif tool_name == "log_unanswered_query":
                        st.markdown(f"📝 **Logged for staff review** → `{tool_input}`")

    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "steps": steps
    })


# ── Handle prefilled question from demo buttons ──
if "prefill" in st.session_state:
    prefill = st.session_state.pop("prefill")
    handle_query(prefill)

# ── Manual chat input ──
user_input = st.chat_input("Type your question here...")
if user_input:
    handle_query(user_input)

# ── Sidebar: Staff Panel ──
st.sidebar.title("📋 Staff Panel")
st.sidebar.caption("Unanswered queries flagged for follow-up:")

if os.path.exists("unanswered_log.txt"):
    with open("unanswered_log.txt", "r") as f:
        logs = f.readlines()
    if logs:
        for log in reversed(logs[-10:]):
            st.sidebar.markdown(f"- {log.strip()}")
        if st.sidebar.button("🗑 Clear Log"):
            open("unanswered_log.txt", "w").close()
            st.rerun()
    else:
        st.sidebar.success("All queries answered ✅")
else:
    st.sidebar.info("No logged queries yet.")

st.sidebar.divider()
st.sidebar.caption("Built with: Groq · Tavily · Streamlit · LangChain-style agentic loop")