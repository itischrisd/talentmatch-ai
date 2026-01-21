from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import streamlit as st
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from talentmatch.agents.api import create_supervised_graph
from talentmatch.config import load_settings
from talentmatch.generation.io import ensure_dirs

_SESSION_MESSAGES_KEY: Final[str] = "ui_messages"


@dataclass(frozen=True, slots=True)
class UiConfig:
    title: str = "TalentMatch UI"
    page_title: str = "TalentMatch"
    page_icon: str = "🧠"
    layout: str = "centered"
    chat_input_placeholder: str = "Ask me to generate an RFP..."
    system_message: str = (
        "You are the TalentMatch assistant. If the user asks to generate an RFP, use the generation tool. "
        "If the user asks to ingest CV PDFs, use the KG ingestion tool. "
        "When a tool produces a file path, mention it in your final answer."
    )


@st.cache_resource
def _graph() -> Any:
    return create_supervised_graph()


def _ensure_state(ui_cfg: UiConfig) -> None:
    if _SESSION_MESSAGES_KEY not in st.session_state:
        st.session_state[_SESSION_MESSAGES_KEY] = [{"role": "system", "content": ui_cfg.system_message}]


def _ui_messages() -> list[dict[str, str]]:
    return st.session_state[_SESSION_MESSAGES_KEY]


def _to_lc_messages(messages: list[dict[str, str]]) -> list[BaseMessage]:
    converted: list[BaseMessage] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            converted.append(SystemMessage(content=content))
        elif role == "user":
            converted.append(HumanMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
    return converted


def _append(role: str, content: str) -> None:
    _ui_messages().append({"role": role, "content": content})


def _render_history() -> None:
    for msg in _ui_messages():
        if msg["role"] == "system":
            continue
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


def _safe_parse_tool_payload(text: str) -> dict[str, Any] | None:
    if not text or not text.strip():
        return None

    stripped = text.strip()

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
        return None
    except Exception:  # noqa: BLE001
        pass

    try:
        parsed = ast.literal_eval(stripped)
        if isinstance(parsed, dict):
            return parsed
        return None
    except Exception:  # noqa: BLE001
        return None


def _extract_latest_artifacts(messages: list[BaseMessage]) -> dict[str, Any]:
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            payload = _safe_parse_tool_payload(str(msg.content))
            if payload and any(k in payload for k in ("pdf_file", "markdown", "rfp")):
                return payload
    return {}


def _render_downloads(artifacts: dict[str, Any]) -> None:
    pdf_file = artifacts.get("pdf_file")
    markdown = artifacts.get("markdown")

    if isinstance(markdown, str) and markdown.strip():
        with st.expander("Generated RFP (Markdown)", expanded=False):
            st.markdown(markdown)

    if isinstance(pdf_file, str) and pdf_file.strip():
        pdf_path = Path(pdf_file)
        if pdf_path.exists() and pdf_path.is_file():
            data = pdf_path.read_bytes()
            st.download_button(
                label="Download RFP PDF",
                data=data,
                file_name=pdf_path.name,
                mime="application/pdf",
            )


def _save_uploaded_cvs() -> int:
    settings = load_settings()
    target_dir = Path(settings.paths.programmers_dir)
    ensure_dirs(target_dir)

    uploaded = st.file_uploader(
        "Upload CV PDFs to ingest",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if not uploaded:
        return 0

    saved = 0
    for f in uploaded:
        dest = target_dir / f.name
        dest.write_bytes(f.getvalue())
        saved += 1
    return saved


def run() -> None:
    """
    Run the Streamlit UI for supervised TalentMatch agents.
    """

    ui_cfg = UiConfig()

    st.set_page_config(page_title=ui_cfg.page_title, page_icon=ui_cfg.page_icon, layout=ui_cfg.layout)
    st.title(ui_cfg.title)

    with st.sidebar:
        st.subheader("CV ingestion")
        saved = _save_uploaded_cvs()
        if saved:
            st.success(f"Saved {saved} file(s) to the configured CV directory.")
        if st.button("Clear chat"):
            st.session_state.pop(_SESSION_MESSAGES_KEY, None)
            st.rerun()

        st.divider()
        st.caption("Tip: ask: “Generate a single RFP PDF”")

    _ensure_state(ui_cfg)
    _render_history()

    user_text = st.chat_input(ui_cfg.chat_input_placeholder)
    if not user_text:
        return

    _append("user", user_text)
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            graph = _graph()
            result = graph.invoke({"messages": _to_lc_messages(_ui_messages())})

            result_messages = result.get("messages", [])
            artifacts = _extract_latest_artifacts(result_messages)

            assistant_text = ""
            for msg in reversed(result_messages):
                if isinstance(msg, AIMessage):
                    assistant_text = str(msg.content)
                    break

            assistant_text = assistant_text.strip() if assistant_text else "Done."
            st.markdown(assistant_text)
            _append("assistant", assistant_text)

            if artifacts:
                _render_downloads(artifacts)
