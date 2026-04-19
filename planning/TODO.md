- [x] Node "Work" is misleading. Originally we wanted something that can connect people based on their work. This should've probably been their views, contributions to their fields, etc, which then may be influencing, critiqued by other persons. 
- [x] Generate final graph along with the final report, as seperate file. This can be derived from the json files output by the agents, which should be easy to map into Mermaid markdown. 
- [x] Create a single page HTML report repsenting all outputs generated. e.g. json, makrdown, for user friendly access. 
- [ ] Externalise prompts to YAML/TOML documents, per AGENT_HARNESS_SUGGESTIONS.md

- [x] Separate synthesis and candidate selection into two nodes, as per AGENT_HARNESS_SUGGESTIONS.md
- [ ] Breath first candidate (person, entity, works, etc) ranking
- [ ] Confidence weighted candidate ranking
- [ ] Implement/Insert HITL step. We need a strategy as for going deep or wide. 

- [x] Neo4j driver code, to add connection pooling
- [ ] Per-node model configuration
- [ ] Tests
- [ ] Improve in-progress UX/UI
- [ ] margre graph export command. e.g. --format mermaid
