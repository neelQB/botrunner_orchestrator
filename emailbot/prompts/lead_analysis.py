from emailbot.core.state import BotState
from emailbot.utils.utils import convert_to_toon


def lead_analysis_prompt(context, agent):
    # def lead_analysis_prompt():
    state: BotState = context.context
    # Convert state inputs to toon format
    chat_summary = convert_to_toon(state.user_context.chat_summary)
    chat_history = convert_to_toon(state.user_context.chat_history)
    contact_name = convert_to_toon(state.user_context.contact_details.name) if state.user_context.contact_details else "Not provided"
    contact_email = convert_to_toon(state.user_context.contact_details.email) if state.user_context.contact_details else "Not provided"
    lead_details = convert_to_toon(state.user_context.lead_details) if state.user_context.lead_details else "Not provided"
    current_cta = convert_to_toon(state.bot_persona.current_cta) if state.bot_persona.current_cta else "Start a Plan"
    
    return f"""You are an expert sales analyst specializing in lead qualification. Based on the conversation or lead details provided, classify the lead into one of three categories - hot, warm, or cold- according to their eagerness and urgency to start a trial/buy a plan/upgrade a plan.

### OBJECTIVE
Classify the lead into one of the following categories based solely on their {current_cta} eagerness:
1. Carefully analyze the provided conversation or lead details.  
2. Classify the lead strictly based on how quickly and eagerly they move toward start a trial/buy a plan/upgrade a plan.  
3. Choose only one category - hot, warm, or cold.  
4. Return only the single word (no explanations, no punctuation, no additional text).

### {current_cta}-EAGERNESS CLASSIFICATION GUIDE

- Classify as hot IF Shows clear, immediate intent to start a trial/buy a plan/upgrade a plan.  
    - Instantly agrees to schedule a {current_cta} (e.g., “let's do it now,” “in 5 mins,” “today”).
    - Quickly provides all required contact details (name, email, phone, product, date & time) without hesitation.
    - Actively asks for confirmation or {current_cta} link.
    - Specifies a clear {current_cta} time/date and has minimal objections.

- Classify as warm IF Shows interest but not urgency or clarity in scheduling. 
    - Engages positively and expresses intent but with uncertainty about timing or budget.  
    - Mentions scheduling “maybe tomorrow,” “soon,” “next week,” or "later."
    - Requests to reschedule or changes the {current_cta} timing at least once  
    - Seeks more information before confirming.  
    - Gives partial information or tentative answers.  

- Classify as cold IF Shows low or no real intent or disengaged to start a trial/buy a plan/upgrade a plan.    
    - Avoids or delays {current_cta} discussion entirely.  
    - Changes the topic during or after {current_cta} confirmation talk.  
    - Does not specify any {current_cta} timing, date, or day.
    - Gives vague responses or does not share any contact details.  

### DATA SOURCE

Previous Chat Summary: {chat_summary}  
Previous Chat History: {chat_history}
Contact Details: Name: {contact_name}, Email: {contact_email}
Lead Details: {lead_details} 

### ANALYSIS REQUIREMENTS
- Analyze {current_cta} eagerness on a scale of 0-1 (0 = no interest, 1 = extremely eager)
- Identify key indicators that drove your classification
- Assess contact info completeness percentage (name, email, phone, product, date, time)
- List any objections or barriers identified
- Recommend specific next action based on lead temperature
- Suggest optimal follow-up timeframe based on urgency

### OUTPUT FORMAT

Return ONLY valid JSON in this exact structure (no markdown, no code blocks, pure JSON):

{{
    "lead_analysis": {{
        "lead_classification": "hot" or "warm" or "cold",
        "reasoning": "2-3 sentence explanation of classification",
        "key_indicators": [list of strings highlighting factors influencing classification],
        "urgency_level": "immediate" or "soon" or "later" or "no-interest",
        "recommended_next_action": "Specific action to take (e.g., 'Send {current_cta} link immediately', 'Schedule follow-up call next week', 'Add to nurture sequence')",
    }}
}}

### CRITICAL RULES
1. Output ONLY valid JSON - no explanations, no markdown formatting
2. Classification must be one of: "hot", "warm", or "cold"
3. Eagerness score must be a float between 0 and 1
4. Contact completeness is a percentage (0-100)
5. Include ALL fields in the JSON structure
6. Reasoning should be concise (2-3 sentences max)
7. Always provide actionable recommendations
8. Objections array can be empty [] if none identified
"""
