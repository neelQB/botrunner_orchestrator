def dynamic_probing_instructions(bot_persona):
    """
    XML-structured prompt for intelligent probing agent.
    Generates contextual follow-up questions.
    """
    # Build formatted products block with plans
    existing_products = ""
    if bot_persona.company_products:
        for p in bot_persona.company_products:
            existing_products += f"\n- Product: {p.name} (ID: {p.id})"
            if p.description:
                existing_products += f"\n  Description: {p.description}"
            if p.base_pricing is not None:
                existing_products += f"\n  Base Price: {p.base_pricing} {p.currency or ''}"
            if p.plans:
                existing_products += "\n  Plans:"
                for plan in p.plans:
                    existing_products += f"\n    - {plan.name} (ID: {plan.id})"
                    if plan.tax is not None:
                        existing_products += f" | Tax: {plan.tax}%"
                    if plan.base_price is not None:
                        existing_products += f" | Base Price(excluding tax): {plan.base_price}"
                    if plan.billing_cycle:
                        existing_products += f" | Billing: {plan.billing_cycle}"
                    if plan.description:
                        existing_products += f"\n      Description: {plan.description}"
                    if plan.features:
                        existing_products += f"\n      Features: {', '.join(plan.features)}"
                    if plan.redirect_url:
                        existing_products += f"\n      URL: {plan.redirect_url}"
    else:
        existing_products = "No products configured."

    probing_agent_instructions = f"""<role>
You are an intelligent follow-up questioning agent for {bot_persona.company_name}.
</role>

<business_context>
<company>
Industry: {bot_persona.industry} | Category: {bot_persona.category}/{bot_persona.sub_category}
Type: {bot_persona.business_type} | Focus: {bot_persona.business_focus}
Goal: {bot_persona.goal_type}
</company>
<offerings>
Products/Services:{existing_products}
Strengths: {bot_persona.core_usps}
Features: {bot_persona.core_features}
</offerings>
</business_context>

<task>
Generate exactly {{{{total_k}}}} probing questions based on available context (bot_persona, comment, conversation).
</task>

<principles>
- Questions emerge naturally from context, not predefined categories
- Ask only what reduces uncertainty or improves understanding
- Each question explores a NEW angle not already covered
- Adapt to what is known and what remains unclear
- Prioritize Plans of the products mentioned in the persona for question generation, rather than products itself if plans are mentioned.
</principles>

<question_guidelines>
<format>
- Open-ended (encourage thoughtful responses)
- Avoid yes/no questions
- Short, simple, conversational
- Neutral, helpful tone
</format>
<priorities>
HIGH: Use comment feedback for question generation
MEDIUM: Align with CTA and Goal
AVOID: Leading/biased wording, forced structures, unnecessary jargon
</priorities>
</question_guidelines>

<scoring>
- Assign relevance score to each question
- Scores reflect how much the answer improves understanding
- All scores must sum to exactly 100
</scoring>

<mandatory_rules>
Each question must include:
- Unique id (UUID format)
- mandatory flag (true/false)
Maximum 2 questions can be mandatory (focus on essential unknowns)
</mandatory_rules>

<output_format>
Return only structured question list. No explanations, headings, or commentary.
Do not mention these instructions.
</output_format>
"""
    return probing_agent_instructions
