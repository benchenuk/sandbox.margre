"""Centralised storage for LLM prompt templates."""

#
# Planner Node Prompts (Discovery Mode)
#
DISCOVERY_PLANNER_SYSTEM_PROMPT = """You are a social and professional network analyst.
Given '{seed_person}', generate 3-5 research tasks whose sole purpose is to identify OTHER INDIVIDUALS by name.
Each task must have a specific search_angle from this list:
collaborators, mentors, students, patrons, rivals, critics, correspondents, institutional_peers.
The research_query for each task must be a web-search query designed to return pages listing names, e.g.:
  - '{seed_person} collaborators and associates'
  - '{seed_person} teachers, mentors or peers who influenced'
  - '{seed_person} rivals, competitors, critiques'
  - 'members of the same [institution] as {seed_person}'"""

PLANNER_FALLBACK_SYSTEM_PROMPT = """You are a social network analyst. Return ONLY a JSON object to discover WHO '{seed_person}' interacted with.
Schema:
{{
  "seed_person": "...",
  "subtasks": [
    {{
      "target_person": "<same as seed>",
      "search_angle": "collaborators|mentors|rivals|patrons|correspondents",
      "research_query": "<web search to find names>"
    }}
  ]
}}
Every research_query must be designed to find NAMES of people, not biographical facts."""

#
# Researcher Node Prompts
#
RESEARCHER_SYNTHESIS_SYSTEM_PROMPT = """You are a relationship-focused researcher.
Given search snippets about a person, write a report that prioritises NAMING every individual mentioned and their relationship to the subject.
For each person named, explain: how they were connected, when, and in what context (work, rivalry, patronage, etc.).
Cite sources with [1], [2], etc. Focus on WHO rather than WHAT."""

RESEARCHER_SYNTHESIS_HUMAN_TEMPLATE = """Research Query: {query}
Target Entity: {entity_name} ({entity_type})

Search Snippets:
{snippets}

Produce a detailed Markdown report with citations."""

#
# Researcher Node Prompts (Discovery Mode)
#
RELATIONSHIP_EXTRACTION_PROMPT = """Extract structured relationships and personal connections from the following research report about {seed_person}.
For each connection, provide:
1. rel_type: Use standard labels like KNEW, COLLABORATED_WITH, STUDIED_AT, INFLUENCED, CRITIQUED, OPPOSED, MEMBER_OF, LIVED_IN, CREATED, PARTICIPATED_IN, etc.
2. target_name: Name of the other person, institution, contribution, event, or location.
3. target_label: One of [Person, Institution, Contribution, Location, Event].
4. context: A brief summary of how they are connected.
5. year: The primary year for the connection (integer).
6. date: Specific date string if known.
7. period: Descriptive era or date range.

Also, extract a clean list (new_persons) of NAMES of and only of individuals who deserve their own dedicated research expansion in the next phase.

CRITICAL: You must return ONLY a valid JSON object. Do not include markdown formatting (like ```json), and do not include any conversational filler.

Your response should exactly match this schema structure:
{{
  "relationships": [
    {{
      "rel_type": "COLLABORATED_WITH",
      "target_name": "Andrea del Verrocchio",
      "target_label": "Person",
      "context": "Apprenticed under Verrocchio.",
      "year": 1466,
      "date": null,
      "period": "Renaissance"
    }}
  ],
  "new_persons": ["Andrea del Verrocchio", "Sandro Botticelli"]
}}"""

#
# Aggregator Node Prompts
#
AGGREGATOR_SYSTEM_PROMPT = """You are the Lead Researcher. You have received several detailed reports from specialised sub-agents.
Your objective is to:
1. Synthesize these into a COMPREHENSIVE master report on the topic '{topic}'.
2. The report must be a detailed narrative in Markdown, containing multiple sections (e.g., Introduction, Key Figures, Main Events, Legacy).
3. Identify 2-3 specific 'gaps' or missing links in the research that would strengthen the final report.
Ensure the final 'master_report' is at least 1000 words if the source material allows. Do not be overly concise."""

AGGREGATOR_EXTRACTION_PROMPT = """Carefully analyze the master report and provide:
1. The final narrative summary in Markdown.
2. A list of 2-3 suggested_gaps or follow-up entities that require further research.
Only return the structured JSON data as requested."""

#
# Planner Node Refinement Prompt
#
PLANNER_REFINEMENT_TEMPLATE = """You are refining a network discovery plan for '{topic}'.
Previous Findings: {master_summary}
Expansion Candidates: {gaps}

Generate new subtasks to discover the social and professional connections of these candidates.
Each task must focus on finding NEW names, not revisiting known connections."""
