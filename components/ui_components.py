"""
Reusable UI components for IAM-Dynamic
"""
import json
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timezone
from typing import Dict, Any, List

from utils.theme import (
    get_risk_color,
    render_risk_badge,
    render_metric_card,
    GRADIENT_START,
    GRADIENT_END
)


def render_metric_card_display(title: str, value: str, subtitle: str = "", color: str = "#7c3aed"):
    """
    Render a styled metric card

    Args:
        title: Card title
        value: Main value to display
        subtitle: Optional subtitle text
        color: Accent color
    """
    st.markdown(
        render_metric_card(title, value, subtitle, color),
        unsafe_allow_html=True
    )


def render_policy_visualization(policy: Dict[str, Any]):
    """
    Render policy as interactive pie chart

    Args:
        policy: IAM policy document
    """
    statements = policy.get("Statement", [])

    if not statements:
        st.info("No policy statements found")
        return

    # Create service breakdown chart
    services = {}
    for stmt in statements:
        if stmt.get("Effect") != "Allow":
            continue

        actions = stmt.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]

        for action in actions:
            if isinstance(action, str):
                # Extract service name from action (e.g., "s3:GetObject" -> "s3")
                service = action.split(":")[0] if ":" in action else action
                services[service] = services.get(service, 0) + 1

    if services:
        # Create custom color sequence
        colors = [GRADIENT_START, GRADIENT_END, "#7c3aed", "#a78bfa", "#c4b5fd"]

        fig = go.Figure(data=[go.Pie(
            labels=list(services.keys()),
            values=list(services.values()),
            hole=0.3,
            marker=dict(colors=colors[:len(services)]),
            textinfo='percent+label',
            textfont_size=12
        )])

        fig.update_layout(
            title_text="<b>Permission Distribution by Service</b>",
            title_font_size=16,
            showlegend=True,
            height=400
        )

        st.plotly_chart(fig, use_container_width=True)


def render_risk_gauge(risk_level: str):
    """
    Render risk assessment gauge chart

    Args:
        risk_level: Risk level (low, medium, high, critical)
    """
    risk_scores = {"low": 25, "medium": 50, "high": 75, "critical": 100}
    score = risk_scores.get(risk_level.lower(), 50)
    color = get_risk_color(risk_level)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"<b>Risk Score: {risk_level.upper()}</b>", 'font_size': 16},
        delta={'reference': 50},
        gauge={
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkgray"},
            'bar': {'color': color},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 25], 'color': '#22c55e'},
                {'range': [25, 50], 'color': '#facc15'},
                {'range': [50, 75], 'color': '#f97316'},
                {'range': [75, 100], 'color': '#dc2626'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': score
            }
        }
    ))

    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)


def render_credential_expiration_timer(expiration: datetime):
    """
    Render countdown timer for credential expiration

    Args:
        expiration: Credential expiration datetime
    """
    now = datetime.now(timezone.utc)
    remaining = expiration - now

    if remaining.total_seconds() <= 0:
        st.error("⚠️ **Credentials have expired!**")
        return

    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)

    # Color-coded warning
    if hours < 1:
        color = "#dc2626"
        icon = "🔴"
        warning_text = "Expires soon!"
    elif hours < 2:
        color = "#f97316"
        icon = "🟠"
        warning_text = "Expiring soon"
    else:
        color = "#22c55e"
        icon = "🟢"
        warning_text = "Valid"

    st.markdown(f"""
    <div style="background: {color}22; border-radius: 12px; padding: 1.5rem;
                border-left: 4px solid {color}; text-align: center; margin: 1rem 0;">
        <div style="font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem; color: {color};">
            {icon} Credential Expiration Timer
        </div>
        <div style="font-size: 3rem; font-weight: 700; color: {color};">
            {hours}h {minutes}m
        </div>
        <div style="font-size: 0.9rem; color: #64748b; margin-top: 0.5rem;">
            Expires at {expiration.strftime('%Y-%m-%d %H:%M:%S')} UTC
        </div>
        <div style="font-size: 0.8rem; color: #64748b;">
            Status: {warning_text}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_quick_templates() -> Dict[str, str]:
    """
    Render quick template buttons for common access patterns

    Returns:
        Dictionary mapping template names to their prompts
    """
    st.subheader("Quick Templates")

    templates = {
        "📂 S3 Read-Only": "I need read-only access to list and get objects from all S3 buckets.",
        "💻 EC2 Observer": "I need to describe instances and view status checks for EC2.",
        "🔧 Lambda Invoker": "I need to invoke Lambda functions in us-east-1.",
        "📊 CloudWatch Logs": "I need to read and filter CloudWatch log streams for application debugging.",
        "🗄️ DynamoDB Reader": "I need to query and scan items from DynamoDB tables in production.",
        "🔑 Secrets Manager": "I need to retrieve specific secrets from AWS Secrets Manager."
    }

    cols = st.columns(3)
    for idx, (label, prompt) in enumerate(templates.items()):
        with cols[idx % 3]:
            if st.button(label, key=f"template_{idx}", use_container_width=True):
                st.session_state.req_text = prompt
                st.rerun()

    return templates


def render_session_history_item(item: Dict[str, Any], index: int):
    """
    Render a single session history item

    Args:
        item: History item dictionary
        index: Item index for unique keys
    """
    risk = item.get('risk', 'unknown')
    risk_color = get_risk_color(risk)
    time_str = item.get('time', 'N/A')
    request_text = item.get('req', '')
    access_key = item.get('access_key', 'N/A')

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
        <div style="background: #f3f4f6; padding: 0.5rem; border-radius: 4px;
                    font-family: monospace; font-size: 0.8rem; color: #374151;">
        {access_key[:20]}...
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_policy_statement_table(policy: Dict[str, Any]):
    """
    Render policy statements as a formatted table

    Args:
        policy: IAM policy document
    """
    statements = policy.get("Statement", [])

    if not statements:
        return

    st.subheader("Policy Statement Breakdown")

    for i, stmt in enumerate(statements):
        effect = stmt.get("Effect", "Allow")
        actions = stmt.get("Action", [])
        resources = stmt.get("Resource", [])
        conditions = stmt.get("Condition")

        # Format actions
        if isinstance(actions, str):
            actions = [actions]
        actions_str = ", ".join(actions[:5])
        if len(actions) > 5:
            actions_str += f" (+{len(actions) - 5} more)"

        # Format resources
        if isinstance(resources, str):
            resources = [resources]
        resources_str = ", ".join(resources[:2])
        if len(resources) > 2:
            resources_str += f" (+{len(resources) - 2} more)"

        # Create statement card
        effect_color = "#22c55e" if effect == "Allow" else "#dc2626"
        st.markdown(f"""
        <div style="background: white; border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem;
                    border-left: 3px solid {effect_color}; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <div style="display: flex; gap: 1rem; font-size: 0.9rem;">
                <div style="min-width: 80px;">
                    <strong>Effect:</strong><br>
                    <span style="color: {effect_color}; font-weight: 600;">{effect}</span>
                </div>
                <div style="flex: 1;">
                    <strong>Actions:</strong><br>
                    <code style="color: #64748b;">{actions_str}</code>
                </div>
                <div style="flex: 1;">
                    <strong>Resources:</strong><br>
                    <code style="color: #64748b;">{resources_str if resources_str else 'All resources (*)'}</code>
                </div>
            </div>
            {f'<div style="margin-top: 0.5rem; font-size: 0.85rem; color: #64748b;"><strong>Conditions:</strong> {str(conditions)}</div>' if conditions else ''}
        </div>
        """, unsafe_allow_html=True)
