# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import os
import re
import json
from typing import Any, List, Dict

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools import AgentTool
from google.adk.workflow import node, START, DEFAULT_ROUTE, Edge, Workflow
from google.adk.events import RequestInput
from google.adk import Context
from google.genai import types
from pydantic import BaseModel, Field

from app.config import config

# Ensure we use Gemini API Key, not Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

# Initialize model
llm = Gemini(
    model=config.model,
    retry_options=types.HttpRetryOptions(attempts=3),
)

# Initialize MCP Toolset connection parameters
from mcp import StdioServerParameters
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams

mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "app.mcp_server"],
            env={
                "PATH": os.getenv("PATH", ""),
            }
        )
    )
)

# -----------------------------------------------------------------------------
# State Schema
# -----------------------------------------------------------------------------
class CareerPilotState(BaseModel):
    user_query: str = ""
    skill_goals: List[Dict[str, Any]] = Field(default_factory=list)
    job_applications: List[Dict[str, Any]] = Field(default_factory=list)
    draft_cover_letter: str = ""
    
    # Audit and security logs
    audit_logs: List[str] = Field(default_factory=list)
    security_violation: bool = False
    security_message: str = ""
    
    # HITL Approval
    approved: bool = False

# -----------------------------------------------------------------------------
# Specialized Sub-Agents
# -----------------------------------------------------------------------------
goal_tracker_agent = LlmAgent(
    name="goal_tracker_agent",
    model=llm,
    instruction=(
        "You are a career goal tracking assistant. Your job is to help users set, track, "
        "and update their professional skill development goals. You can output goal logs "
        "or suggest learning timelines. Return a concise, structured update of their goals."
    ),
    tools=[mcp_toolset],
)

cover_letter_agent = LlmAgent(
    name="cover_letter_agent",
    model=llm,
    instruction=(
        "You are an expert resume and cover letter writing assistant. Your job is to write, "
        "refine, or tailor professional resumes and cover letters for specific roles. "
        "Ensure the output highlights the user's relevant experience and fits the target job description. "
        "Use MCP tools to parse job descriptions or retrieve templates to structure the resume/cover letter."
    ),
    tools=[mcp_toolset],
)

# -----------------------------------------------------------------------------
# Orchestrator Agent
# -----------------------------------------------------------------------------
orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    model=llm,
    instruction=(
        "You are the CareerPilot orchestrator. You help users navigate their career path, "
        "including setting skill goals, tracking job applications, and writing tailored cover letters. "
        "Delegate tasks to goal_tracker_agent and cover_letter_agent tools as needed. "
        "If a cover letter is successfully drafted, inform the user that it needs their final approval, "
        "and specify that human review is required."
    ),
    tools=[AgentTool(agent=goal_tracker_agent), AgentTool(agent=cover_letter_agent)],
)

# -----------------------------------------------------------------------------
# Workflow Nodes
# -----------------------------------------------------------------------------
@node
def security_checkpoint(ctx: Context, node_input: Any):
    query = ""
    if isinstance(node_input, dict):
        query = node_input.get("message", "")
    elif isinstance(node_input, str):
        query = node_input
    
    # 1. PII Scrubbing (Regex for email and phone numbers)
    email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    phone_regex = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
    
    scrubbed_query = re.sub(email_regex, "[REDACTED_EMAIL]", query)
    scrubbed_query = re.sub(phone_regex, "[REDACTED_PHONE]", scrubbed_query)
    ctx.state["user_query"] = scrubbed_query
    
    # 2. Prompt Injection Detection (Keyword detection)
    injection_keywords = ["ignore previous instructions", "system prompt", "dan mode", "you are now a", "override safety"]
    has_injection = any(kw in query.lower() for kw in injection_keywords)
    
    # 3. Domain-specific rule (Check for fraudulent/harmful job applications)
    banned_roles = ["hacker", "scammer", "bank robber", "drug dealer", "assassin"]
    has_banned_role = any(role in query.lower() for role in banned_roles)
    
    # Initialize audit logs list if not present
    audit_logs = ctx.state.get("audit_logs") or []
    
    if has_injection or has_banned_role:
        severity = "CRITICAL"
        reason = "Prompt Injection detected" if has_injection else "Banned role requested"
        audit_entry = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "event": "security_violation",
            "severity": severity,
            "reason": reason,
            "input_preview": query[:50]
        }
        ctx.state["security_violation"] = True
        ctx.state["security_message"] = f"Access Denied: {reason}."
        audit_logs.append(json.dumps(audit_entry))
        ctx.state["audit_logs"] = audit_logs
        ctx.route = "security_event"
        return ctx.state["security_message"]
    else:
        severity = "INFO"
        audit_entry = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "event": "input_verified",
            "severity": severity,
            "input_preview": scrubbed_query[:50]
        }
        audit_logs.append(json.dumps(audit_entry))
        ctx.state["audit_logs"] = audit_logs
        ctx.route = "safe"
        return scrubbed_query


@node(rerun_on_resume=True)
async def orchestrator_node(ctx: Context, node_input: Any):
    result = await ctx.run_node(orchestrator_agent, node_input=node_input)
    
    # Check if a cover letter draft was generated
    if "cover letter" in result.lower() or "dear hiring manager" in result.lower():
        ctx.state["draft_cover_letter"] = result
        ctx.route = "needs_approval"
    else:
        ctx.route = "direct"
        
    return result

@node(rerun_on_resume=True)
async def human_approval(ctx: Context, node_input: Any):
    interrupt_id = "user_approval"
    response = ctx.resume_inputs.get(interrupt_id)
    
    if response is not None:
        user_input = response.get("result", "")
        if "approve" in user_input.lower() or "yes" in user_input.lower():
            ctx.state["approved"] = True
            ctx.route = "direct"
            return f"Cover letter approved and finalized!\n\n{ctx.state.get('draft_cover_letter')}"
        else:
            ctx.state["approved"] = False
            # Re-run orchestrator with user's feedback
            feedback = f"User requested changes to the cover letter draft: '{user_input}'. Please revise the cover letter."
            result = await ctx.run_node(orchestrator_agent, node_input=feedback)
            if "cover letter" in result.lower() or "dear hiring manager" in result.lower():
                ctx.state["draft_cover_letter"] = result
                ctx.route = "needs_approval"
                return result
            else:
                ctx.route = "direct"
                return result
    else:
        return RequestInput(
            interrupt_id=interrupt_id,
            message=f"Please review the cover letter draft below. Type 'approve' to finalize or describe changes:\n\n{ctx.state.get('draft_cover_letter')}"
        )

@node
def security_event_node(ctx: Context, node_input: Any):
    return ctx.state.get("security_message")

@node
def final_output_node(ctx: Context, node_input: Any):
    return node_input

# -----------------------------------------------------------------------------
# Workflow Definition
# -----------------------------------------------------------------------------
edges = [
    Edge(from_node=START, to_node=security_checkpoint),
    Edge(from_node=security_checkpoint, to_node=orchestrator_node, route="safe"),
    Edge(from_node=security_checkpoint, to_node=security_event_node, route="security_event"),
    Edge(from_node=orchestrator_node, to_node=human_approval, route="needs_approval"),
    Edge(from_node=orchestrator_node, to_node=final_output_node, route="direct"),
    Edge(from_node=human_approval, to_node=human_approval, route="needs_approval"),
    Edge(from_node=human_approval, to_node=final_output_node, route="direct"),
]

root_agent = Workflow(
    name="career_pilot_workflow",
    description="Orchestrator workflow for career goal tracking and cover letter drafting.",
    edges=edges,
    state_schema=CareerPilotState,
)

app = App(
    root_agent=root_agent,
    name="app",
)
