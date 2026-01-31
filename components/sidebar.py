"""
Enhanced sidebar with persistent history and search
"""
import os
import streamlit as st
from typing import List, Dict, Any, Optional

from utils.theme import get_risk_color


def render_sidebar(
    history: List[Dict[str, Any]],
    db_service=None,
    session_count: int = 0,
    llm_provider: str = "gemini",
    gemini_model: str = "gemini-1.5-pro",
    account_id: str = "unknown"
):
    """
    Render enhanced sidebar with search and filters

    Args:
        history: List of history items from session
        db_service: Optional database service for persistent history
        session_count: Number of requests this session
        llm_provider: Current LLM provider
        gemini_model: Current model name
        account_id: AWS account ID
    """
    with st.sidebar:
        st.header("📜 Session History")

        # Search and filter
        search_term = st.text_input("🔍 Search", placeholder="Search requests...", key="sidebar_search")

        risk_levels = ["All", "Low", "Medium", "High", "Critical"]
        risk_filter = st.selectbox("Filter by Risk", risk_levels, index=0, key="sidebar_risk_filter")

        # Apply filters to session history
        filtered_history = history
        if search_term:
            filtered_history = [
                item for item in history
                if search_term.lower() in item.get("req", "").lower()
            ]
        if risk_filter != "All":
            filtered_history = [
                item for item in filtered_history
                if item.get("risk", "").lower() == risk_filter.lower()
            ]

        # Statistics
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total", len(history))
        with col2:
            st.metric("Session", session_count)

        st.divider()

        # Render history items
        if filtered_history:
            for i, item in enumerate(reversed(filtered_history[:20])):  # Show last 20
                risk = item.get('risk', 'unknown')
                risk_color = get_risk_color(risk)
                time_str = item.get('time', 'N/A')
                request_text = item.get('req', '')
                access_key = item.get('access_key', 'N/A')

                with st.expander(f"{time_str} - {risk.upper()}", expanded=False):
                    st.caption(request_text[:100] + "..." if len(request_text) > 100 else request_text)
                    st.code(access_key, language="bash")
        else:
            if search_term or risk_filter != "All":
                st.info("No matching requests found.")
            else:
                st.info("No requests this session.")

        # Database history section (if db_service available)
        if db_service:
            st.divider()
            st.subheader("💾 Persistent History")

            if st.button("🔄 Load from Database", key="load_db_history"):
                try:
                    recent = db_service.get_recent_requests(limit=20)
                    st.info(f"Found {len(recent)} requests in database")
                    for item in recent:
                        with st.expander(f"{item['created_at']} - {item['risk_level'].upper()}", expanded=False):
                            st.caption(item['request_text'][:80] + "...")
                            st.caption(f"Status: {item['status']}")
                except Exception as e:
                    st.error(f"Failed to load history: {e}")

            # Export all history
            st.divider()
            if st.button("⬇️ Export All History", key="export_history"):
                try:
                    csv_data = db_service.export_history("csv")
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=f"iam_history_{db_service.db_path.replace('.db', '')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Failed to export: {e}")

        st.divider()

        # Configuration info
        st.subheader("⚙️ Configuration")
        st.caption(f"🤖 LLM: {llm_provider.upper()}")
        st.caption(f"🧠 Model: {gemini_model}")
        st.caption(f"🔐 Account: {account_id}")

        # Database info (if available)
        if db_service:
            try:
                stats = db_service.get_statistics()
                st.divider()
                st.subheader("📊 Statistics")
                st.caption(f"Total Requests: {stats['total_requests']}")
                if stats['by_risk_level']:
                    for risk, count in stats['by_risk_level'].items():
                        st.caption(f"{risk.upper()}: {count}")
            except Exception:
                pass


def render_history_item(item: Dict[str, Any], index: int):
    """
    Render a single history item

    Args:
        item: History item dictionary
        index: Item index for unique keys
    """
    risk = item.get('risk', 'unknown')
    risk_color = get_risk_color(risk)
    time_str = item.get('time', item.get('created_at', 'N/A'))
    request_text = item.get('req', item.get('request_text', ''))
    access_key = item.get('access_key', 'N/A')
    status = item.get('status', 'unknown')

    st.markdown(f"""
    <div style="background: white; border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem;
                border-left: 3px solid {risk_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <div style="font-weight: 600; font-size: 0.9rem;">{time_str}</div>
            <div style="background: {risk_color}; color: white; padding: 0.25rem 0.75rem;
                        border-radius: 12px; font-size: 0.7rem; font-weight: 600;">
                {risk.upper()}
            </div>
        </div>
        <div style="color: #64748b; font-size: 0.85rem; margin-bottom: 0.5rem;">
            {request_text[:80]}{'...' if len(request_text) > 80 else ''}
        </div>
        {f'<div style="font-size: 0.75rem; color: #64748b;">Status: {status}</div>' if status != 'unknown' else ''}
        <div style="background: #f3f4f6; padding: 0.5rem; border-radius: 4px;
                    font-family: monospace; font-size: 0.8rem; color: #374151;">
        {access_key[:20]}...
        </div>
    </div>
    """, unsafe_allow_html=True)
