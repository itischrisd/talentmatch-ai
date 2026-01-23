from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import streamlit as st
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from talentmatch.agents.api import create_supervised_graph
from talentmatch.config import Settings, load_settings
from talentmatch.generation.io import ensure_dirs
from talentmatch.infra.logging import configure_logging

logger = logging.getLogger(__name__)

_SESSION_MESSAGES_KEY: Final[str] = "ui_messages"


@dataclass(frozen=True, slots=True)
class UiConfig:
    """
    Streamlit UI settings and text.
    """

    page_title: str = "TalentMatch"
    page_icon: str = "🧩"
    layout: str = "wide"

    title: str = "TalentMatch"
    chat_input_placeholder: str = "Give me a task or ask about what you can do..."


def _append(role: str, content: str) -> None:
    st.session_state[_SESSION_MESSAGES_KEY].append({"role": role, "content": content})


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


def _render_history() -> None:
    for msg in _ui_messages():
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            continue
        with st.chat_message("user" if role == "user" else "assistant"):
            st.markdown(content)


def _extract_latest_artifacts(messages: list[BaseMessage]) -> dict[str, Any]:
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            try:
                payload = ast.literal_eval(str(msg.content))
            except (ValueError, SyntaxError):
                continue
            if isinstance(payload, dict) and "artifacts" in payload:
                artifacts = payload.get("artifacts") or {}
                if isinstance(artifacts, dict):
                    return artifacts
    return {}


def _render_downloads(artifacts: dict[str, Any]) -> None:
    if not artifacts:
        return

    st.divider()
    st.subheader("Downloads")

    for key, value in artifacts.items():
        if not value:
            continue

        path = Path(str(value))
        if not path.exists():
            continue

        data = path.read_bytes()
        if path.suffix.lower() == ".pdf":
            st.download_button(
                label=f"Download {key}",
                data=data,
                file_name=path.name,
                mime="application/pdf",
            )
        else:
            st.download_button(
                label=f"Download {key}",
                data=data,
                file_name=path.name,
                mime="application/octet-stream",
            )


def _save_uploaded_files(
        *,
        label: str,
        uploader_key: str,
        target_dir: Path,
        allowed_types: list[str],
) -> int:
    uploaded = st.file_uploader(
        label,
        type=allowed_types,
        accept_multiple_files=True,
        key=uploader_key,
    )

    if not uploaded:
        return 0

    ensure_dirs(target_dir)

    saved = 0
    for f in uploaded:
        dest = target_dir / f.name
        dest.write_bytes(f.getvalue())
        saved += 1

    logger.info("Staged %s file(s) into %s", saved, str(target_dir))
    return saved


@st.cache_resource
def _graph() -> Any:
    logger.info("Initializing supervisor graph (cached resource)")
    return create_supervised_graph()


def _ensure_state() -> None:
    if _SESSION_MESSAGES_KEY not in st.session_state:
        st.session_state[_SESSION_MESSAGES_KEY] = [
            {
                "role": "system",
                "content": (
                    "You are TalentMatch supervisor. Use tools when appropriate. "
                    "When asked to ingest staged files, call the ingestion tool."
                ),
            }
        ]


def _staging_panel(settings: Settings) -> dict[str, Any]:
    cvs_dir = Path(settings.paths.programmers_dir)
    rfps_dir = Path(settings.paths.rfps_dir)
    projects_dir = Path(settings.paths.projects_dir)

    ensure_dirs(cvs_dir, rfps_dir, projects_dir)

    with st.sidebar:
        st.subheader("File staging")
        st.caption("Upload files to stage them for ingestion. Then ask: “Ingest staged files”.")

        with st.expander("CV PDFs", expanded=False):
            _save_uploaded_files(
                label="Upload CV PDFs",
                uploader_key="upload_cvs",
                target_dir=cvs_dir,
                allowed_types=["pdf"],
            )

        with st.expander("RFP PDFs", expanded=False):
            _save_uploaded_files(
                label="Upload RFP PDFs",
                uploader_key="upload_rfps",
                target_dir=rfps_dir,
                allowed_types=["pdf"],
            )

        with st.expander("Structured data", expanded=False):
            _save_uploaded_files(
                label="Upload structured files",
                uploader_key="upload_structured",
                target_dir=projects_dir,
                allowed_types=["json", "xml", "yaml", "yml"],
            )

        with st.expander("Paths", expanded=False):
            st.json(
                {
                    "programmers_dir": str(cvs_dir),
                    "rfps_dir": str(rfps_dir),
                    "projects_dir": str(projects_dir),
                    "archive_dir": str(Path(settings.paths.archive_dir)),
                }
            )

        if st.button("Clear chat", type="secondary"):
            st.session_state.pop(_SESSION_MESSAGES_KEY, None)
            st.rerun()

    return {
        "programmers_dir": str(cvs_dir),
        "rfps_dir": str(rfps_dir),
        "projects_dir": str(projects_dir),
    }


def run() -> None:
    """
    Run the Streamlit UI for supervised TalentMatch agents.
    """

    settings = load_settings()
    configure_logging(settings=settings)

    ui_cfg = UiConfig()

    st.set_page_config(page_title=ui_cfg.page_title, page_icon=ui_cfg.page_icon, layout=ui_cfg.layout)
    _staging_panel(settings)

    st.title(ui_cfg.title)

    _ensure_state()
    _render_history()

    user_text = st.chat_input(ui_cfg.chat_input_placeholder)
    if not user_text:
        return

    logger.info("UI received user message (%s chars)", len(user_text))

    _append("user", user_text)
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            graph = _graph()
            logger.info("Invoking supervisor graph")
            result = graph.invoke({"messages": _to_lc_messages(_ui_messages())})
            logger.info("Supervisor graph invocation finished")

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
                logger.info("Rendering %s artifact(s) for download", len(artifacts))
                _render_downloads(artifacts)
