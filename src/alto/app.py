"""Streamlit Frontend: Chat → Teaching Interface.

Theory-backed, self-supervised, minimal viable product.
"""

import streamlit as st
from dotenv import load_dotenv
from alto.config import get_config
from alto.engine import Engine

# 加载 .env 配置，供前端自动填充默认值
load_dotenv()
_cfg = get_config()

st.set_page_config(
    page_title="Language Learning",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ==================== CSS Styling ====================
st.markdown("""
<style>
.construction-card {
    padding: 12px;
    border-radius: 8px;
    border-left: 4px solid #4CAF50;
    background-color: #1e1e1e;
    margin: 8px 0;
}
.activation-bar {
    height: 8px;
    border-radius: 4px;
    background: linear-gradient(90deg, #f44336 0%, #ff9800 50%, #4CAF50 100%);
}
.teach-mode-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: bold;
    background: #2196F3;
    color: white;
}
.diagnosis-box {
    font-size: 12px;
    color: #888;
    padding: 8px;
    border-radius: 4px;
    background: #1a1a1a;
    margin-top: 4px;
}
</style>
""", unsafe_allow_html=True)


# ==================== Session State ====================
def init_state():
    defaults = {
        "engine": None,
        "messages": [],
        "mode": "setup",
        "lesson": None,
        "target_cxn": None,
        "show_diagnosis": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ==================== Setup Page ====================
if st.session_state.mode == "setup":
    st.title("🧠 语言学习系统")
    st.caption("Emergent Construction-based Language Mentor")

    st.markdown("""
    ### Theory Foundation
    - **Construction Grammar (CxG)**: Language knowledge = form-meaning pairings
    - **ACT-R**: Declarative → Procedural → Automated skill acquisition
    - **ZPD/Scaffolding**: Adaptive teaching at the right difficulty level
    - **Neuro-Symbolic AI**: spaCy syntax + LLM semantics for error diagnosis
    - **Self-supervised**: Zero manual annotation needed
    """)

    # 从 .env 读取默认值，自动填充表单
    default_base_url = _cfg.llm.base_url or "https://api.moonshot.cn/v1"
    default_model = _cfg.llm.model_name or "moonshot-v1-8k"
    default_key = _cfg.llm.api_key or ""
    has_env_key = bool(default_key)

    with st.form("config"):
        col1, col2 = st.columns(2)
        with col1:
            base_url = st.text_input("API Base URL", value=default_base_url)
            api_key = st.text_input("API Key", type="password", value=default_key)
            model_name = st.text_input("Model", value=default_model)
        with col2:
            user_id = st.text_input("Learner ID", value="learner_001")
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("🚀 Launch", use_container_width=True)

        if submitted:
            effective_key = api_key or default_key
            if not effective_key:
                st.error("API Key is required（请在 .env 或上方输入框中填入）")
            else:
                try:
                    st.session_state.engine = Engine(
                        user_id=user_id,
                        api_key=effective_key,
                        base_url=base_url,
                        model_name=model_name,
                    )
                    st.session_state.mode = "chat"
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": (
                            "Hi! I'm your language learning partner. "
                            "Let's chat naturally — I'll notice patterns you might want to practice "
                            "and suggest focused exercises when the time is right."
                        ),
                    })
                    st.rerun()
                except Exception as e:
                    st.error(f"Launch failed: {e}")


# ==================== Chat Mode ====================
elif st.session_state.mode == "chat":
    # Sidebar: Dashboard
    with st.sidebar:
        st.subheader("📊 Learner State")

        if st.session_state.engine:
            try:
                dash = st.session_state.engine.get_dashboard_data()
                stats = dash["stats"]

                st.metric("Constructions", stats["total"])
                col_m, col_l, col_w = st.columns(3)
                col_m.metric("Mastered", stats["mastered"])
                col_l.metric("Learning", stats["learning"])
                col_w.metric("Weak", stats["weak"])

                st.divider()
                st.markdown("**Construction Activation**")
                for c in dash["constructions"][:8]:
                    color = "🟢" if c["activation"] > 0.7 else "🟡" if c["activation"] > 0.3 else "🔴"
                    st.progress(
                        c["activation"],
                        text=f"{color} {c['id'][:25]} ({c['activation']:.0%})",
                    )

                st.divider()

                # Conversation Context
                conv = dash.get("conversation", {})
                if conv.get("topic") or conv.get("summary"):
                    st.markdown("**🗣️ Conversation**")
                    if conv.get("topic"):
                        st.caption(f"Topic: {conv['topic']}")
                    if conv.get("mood"):
                        st.caption(f"Mood: {conv['mood']}")
                    if conv.get("summary"):
                        with st.expander("Summary"):
                            st.caption(conv["summary"])
                    if conv.get("key_facts"):
                        with st.expander("Key Facts"):
                            for f in conv["key_facts"]:
                                st.caption(f"• {f['fact']}")
                    st.divider()

                st.caption(f"Session: {dash['interactions']} interactions | Turns: {conv.get('total_turns', 0)}")

                if st.button("🔄 Reset Memory", type="secondary"):
                    import shutil
                    try:
                        shutil.rmtree("./data/memory")
                        st.success("Memory cleared")
                        st.rerun()
                    except Exception:
                        pass
            except Exception:
                st.info("Start chatting to see your learning state.")

        st.divider()
        st.caption("v0.1.0 | CxG + ACT-R + ZPD")

    # Main: Chat
    st.title("💬 Chat")
    st.caption("Free conversation → Automatic construction detection → Targeted practice")

    # Diagnosis toggle
    col_toggle, _ = st.columns([1, 4])
    with col_toggle:
        st.session_state.show_diagnosis = st.toggle("Show diagnosis", value=False)

    # Messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    if prompt := st.chat_input("Type in English..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Analyzing..."):
            result = st.session_state.engine.process_chat(prompt)

        reply = result.get("reply", "...")
        st.session_state.messages.append({"role": "assistant", "content": reply})

        # Show diagnosis if enabled
        if st.session_state.show_diagnosis and result.get("diagnosis"):
            diag = result["diagnosis"]
            with st.chat_message("assistant"):
                st.markdown(f"""
                <div class="diagnosis-box">
                🔍 <b>{diag.get('target_cxn', 'N/A')}</b> |
                Error: <b>{diag.get('error_type', 'none')}</b> |
                Systematic: <b>{diag.get('is_systematic', False)}</b> |
                ZPD: <b>{diag.get('zpd_recommendation', 'N/A')}</b>
                </div>
                """, unsafe_allow_html=True)

        # Teaching suggestion banner
        if result.get("should_teach") and result.get("suggested_target"):
            target = result["suggested_target"]
            cols = st.columns([3, 1])
            with cols[0]:
                st.info(f"💡 Detected learning opportunity: **{target}**")
            with cols[1]:
                if st.button(f"Practice {target}", key=f"teach_{target}", use_container_width=True):
                    with st.spinner("Generating lesson..."):
                        lesson_data = st.session_state.engine.enter_teaching(target)
                    st.session_state.lesson = lesson_data
                    st.session_state.target_cxn = target
                    st.session_state.mode = "teach"
                    st.rerun()

        st.rerun()


# ==================== Teaching Mode ====================
elif st.session_state.mode == "teach":
    lesson = st.session_state.lesson
    target = st.session_state.target_cxn

    if lesson and st.session_state.engine:
        state = st.session_state.engine.declarative.get_state(target)
        activation = state.activation if state else 0.0

        # Header
        st.title(f"🎯 {target}")
        cols = st.columns([1, 1, 1])
        with cols[0]:
            st.caption(f"Activation: {activation:.0%}")
            st.progress(activation)
        with cols[1]:
            stage = (
                "📖 Declarative" if activation < 0.25 else
                "🔨 Associative" if activation < 0.60 else
                "⚡ Procedural" if activation < 0.85 else
                "✨ Autonomous"
            )
            st.caption(f"Stage: **{stage}**")
        with cols[2]:
            st.caption(f"Exposures: {state.exposure_count if state else 0}")

        st.divider()

        # Lesson content
        lesson_data = lesson.get("lesson", {})

        st.markdown(f"### {lesson_data.get('title', 'Practice')}")
        st.info(lesson_data.get("content", ""))

        st.markdown("**📝 Exercise**")
        st.write(lesson_data.get("exercise", "Please complete the exercise."))

        if lesson_data.get("hints"):
            with st.expander("💡 Hints"):
                for h in lesson_data["hints"]:
                    st.markdown(f"- {h}")

        # Answer input
        answer = st.text_area("Your answer:", key="exercise_answer", height=80)

        col_submit, col_back = st.columns([1, 1])

        with col_submit:
            if st.button("✅ Submit", use_container_width=True, type="primary"):
                if answer.strip():
                    with st.spinner("Evaluating..."):
                        eval_result = st.session_state.engine.evaluate_exercise(answer)

                    if eval_result.get("success"):
                        st.success("✅ Correct!")
                        st.balloons()
                    else:
                        st.error("❌ Needs adjustment")

                    st.markdown(f"**Feedback:** {eval_result.get('feedback', '')}")

                    new_act = eval_result.get("new_activation", 0)
                    st.progress(new_act, text=f"Updated activation: {new_act:.0%}")

                    if eval_result.get("should_continue"):
                        if st.button("🔄 Continue Practice", key="continue"):
                            with st.spinner("Generating new exercise..."):
                                new_lesson = st.session_state.engine.enter_teaching(target)
                            st.session_state.lesson = new_lesson
                            st.rerun()
                    else:
                        st.success("🎉 You're getting comfortable with this pattern!")
                        if st.button("↩ Return to Chat", use_container_width=True):
                            with st.spinner("Wrapping up..."):
                                result = st.session_state.engine.exit_teaching()
                            st.session_state.mode = "chat"
                            st.session_state.lesson = None
                            st.session_state.target_cxn = None
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": result.get("reply", "Let's keep chatting!"),
                            })
                            st.rerun()

        with col_back:
            if st.button("↩ Back to Chat", use_container_width=True):
                with st.spinner("Wrapping up..."):
                    result = st.session_state.engine.exit_teaching()
                st.session_state.mode = "chat"
                st.session_state.lesson = None
                st.session_state.target_cxn = None
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result.get("reply", "Let's keep chatting!"),
                })
                st.rerun()

    else:
        st.error("Lesson data missing")
        if st.button("↩ Back to Chat"):
            st.session_state.mode = "chat"
            st.rerun()
