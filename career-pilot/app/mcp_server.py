import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CareerPilot MCP Server")

@mcp.tool()
def get_job_market_trends(role: str) -> str:
    """Gets job market demand, average salary range, and key skills required for a role.
    
    Args:
        role: The job title/role to look up trends for (e.g. 'Software Engineer').
    """
    role_lower = role.lower()
    if "software" in role_lower or "developer" in role_lower or "engineer" in role_lower:
        return (
            "Job Market Trends for Software Engineering:\n"
            "- Demand: High (12% growth projected through 2030)\n"
            "- Average Salary: $115,000 - $160,000 USD\n"
            "- Top Required Skills: Python, TypeScript, System Design, Cloud Architecture (GCP/AWS)"
        )
    elif "data" in role_lower or "analyst" in role_lower or "scientist" in role_lower:
        return (
            "Job Market Trends for Data Science/Analytics:\n"
            "- Demand: High (15% growth projected through 2030)\n"
            "- Average Salary: $105,000 - $145,000 USD\n"
            "- Top Required Skills: Python, SQL, Machine Learning, Statistics, Tableau/PowerBI"
        )
    else:
        return (
            f"Job Market Trends for {role}:\n"
            "- Demand: Moderate (5% growth projected)\n"
            "- Average Salary: $75,000 - $110,000 USD\n"
            "- Top Required Skills: Communication, Project Management, Domain Expertise"
        )

@mcp.tool()
def search_local_companies(industry: str, location: str) -> str:
    """Finds top companies hiring in a specific industry and city.
    
    Args:
        industry: The industry/field to search (e.g. 'Tech', 'Finance').
        location: The city or region (e.g. 'San Francisco').
    """
    ind = industry.lower()
    if "tech" in ind or "software" in ind or "it" in ind:
        return f"Top hiring Tech/Software companies in {location}:\n- Alphabet (Google)\n- Microsoft\n- Salesforce\n- Local Innovators & Startups"
    elif "finance" in ind or "bank" in ind:
        return f"Top hiring Finance/Banking companies in {location}:\n- JPMorgan Chase\n- Goldman Sachs\n- Fidelity Investments\n- Regional Banking & Credit Unions"
    else:
        return f"Top hiring companies in the {industry} industry in {location}:\n- Acme Corporation\n- Global Solutions Inc.\n- Regional Services Group"

@mcp.tool()
def get_resume_templates(field: str) -> str:
    """Provides professional markdown formatting templates for resumes in a specific field.
    
    Args:
        field: The career field (e.g. 'Tech', 'General').
    """
    f = field.lower()
    if "tech" in f or "software" in f:
        return (
            "# Tech Resume Template\n"
            "## Contact\nName | Email | GitHub | LinkedIn\n"
            "## Skills\n- Languages: Python, TypeScript, Go\n- Tools: Docker, Kubernetes, Git\n"
            "## Experience\n**Role Title** @ Company (Date - Present)\n- Bullet point 1\n- Bullet point 2\n"
            "## Projects\n**Project Name**\n- Bullet point on tech stack and outcome"
        )
    else:
        return (
            "# General Professional Resume Template\n"
            "## Contact\nName | Email | Phone | LinkedIn\n"
            "## Summary\nBrief professional summary\n"
            "## Work History\n**Role Title** @ Company (Date - Date)\n- Bullet point 1\n- Bullet point 2\n"
            "## Education\nDegree @ University"
        )

@mcp.tool()
def parse_job_description(text: str) -> str:
    """Parses a job description to extract core requirements, soft skills, and key keywords.
    
    Args:
        text: The raw job description text.
    """
    requirements = []
    soft_skills = []
    
    lines = text.split('\n')
    for line in lines:
        l = line.lower()
        if "years" in l or "experience" in l or "degree" in l or "bachelor" in l or "must have" in l or "required" in l:
            requirements.append(line.strip())
        if "team" in l or "communication" in l or "collaborate" in l or "passion" in l or "leadership" in l:
            soft_skills.append(line.strip())
            
    reqs_str = "\n- ".join(requirements[:4]) if requirements else "No specific technical requirements identified."
    soft_str = "\n- ".join(soft_skills[:3]) if soft_skills else "No specific soft skills identified."
    
    return (
        f"Parsed Job Insights:\n"
        f"### Technical/Experience Requirements:\n- {reqs_str}\n\n"
        f"### Soft Skills & Collaboration:\n- {soft_str}"
    )

if __name__ == "__main__":
    mcp.run()
