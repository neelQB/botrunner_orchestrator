"""
Activity Summary Prompt - Generates a consolidated activity summary.
"""

def activity_summary_instructions(current_summary: str = "", activities: list = None):
    activities_text = ""
    if activities:
        for idx, act in enumerate(activities):
            activities_text += f"\nActivity {idx+1}:\n"
            activities_text += f"- Stage: {act.get('stage', 'N/A')}\n"
            activities_text += f"- Description: {act.get('description', 'N/A')}\n"
            activities_text += f"- Title: {act.get('title', 'N/A')}\n"
            activities_text += f"- Source: {act.get('contact_source', 'N/A')}\n"
    else:
        activities_text = "No new activities provided."

    return f"""
You are an AI assistant tasked with updating and consolidating a customer's activity summary into a single, cohesive narrative.

Current Summary:
{current_summary if current_summary else "No existing summary."}

New Activities to Consolidate:
{activities_text}

Task:
Generate a single, unified "Main Activity Summary" that integrates all the new activities into the existing summary.

Requirements:
1. CONSOLIDATE: Do NOT list activities stage-by-stage or separately. Combine everything into a single professional narrative.
2. Bullet Points: Format the unified summary using bullet points for clarity.
3. Content: Focus on the overall status, key decisions, and next steps across the entire relationship.
4. Tone: Keep it professional, concise, and objective.
5. Avoid Redundancy: Ensure the summary doesn't repeat information already present in the current summary.

Output Format:
strict json
{{
    "activity_summary": "<single consolidated bulleted summary>",
}}
"""
